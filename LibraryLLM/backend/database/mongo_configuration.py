"""Explicit Mongo authentication qualification; legacy development remains opt-in by default.

Never logs a URI or a driver exception. The anonymous connection is a deny-only
authorization probe, never an application client or an authentication fallback.
"""
import os
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pymongo import MongoClient, timeout
from pymongo.errors import OperationFailure
from pymongo.uri_parser import parse_uri


class MongoConfigurationError(RuntimeError):
    """Safe fixed-code startup error, without credential-bearing driver details."""


@dataclass(frozen=True)
class MongoSettings:
    uri: str | None = field(repr=False)
    database: str
    authenticated: bool


def settings(environ=None, *, default_uri=None):
    env = os.environ if environ is None else environ
    mode = env.get('LUMINAR_MONGO_MODE', 'DEVELOPMENT').upper()
    if mode not in {'DEVELOPMENT', 'AUTHENTICATED'}:
        raise MongoConfigurationError('MONGO_MODE_INVALID')
    uri = env.get('MONGO_URI', default_uri)
    database = env.get('MONGO_DB_NAME', 'luminar_library')
    if mode == 'DEVELOPMENT':
        return MongoSettings(uri, database, False)
    if not uri or not env.get('MONGO_DB_NAME'):
        raise MongoConfigurationError('MONGO_AUTH_SETTINGS_REQUIRED')
    try:
        parsed = parse_uri(uri)
        options = {k.lower(): v for k, v in parsed['options'].items()}
        valid = (parsed['username'] and parsed['password'] and parsed['database'] == database
                 and options.get('authsource')
                 and options.get('authmechanism', 'SCRAM-SHA-256') in {'SCRAM-SHA-256', 'SCRAM-SHA-1'})
    except Exception:
        raise MongoConfigurationError('MONGO_AUTH_URI_INVALID') from None
    if not valid:
        raise MongoConfigurationError('MONGO_AUTH_SETTINGS_REQUIRED')
    return MongoSettings(uri, database, True)


def _deny_probe_uri(uri):
    parts = urlsplit(uri)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('auth')]
    return urlunsplit((parts.scheme, parts.netloc.rsplit('@', 1)[-1], parts.path, urlencode(query), ''))


def _qualify(client, config):
    # One deadline for readiness only; steady-state query/socket/retry behavior
    # remains under existing service controls, including long native builds.
    with timeout(10):
        auth = client[config.database].command('connectionStatus', showPrivileges=False)['authInfo']
        parsed = parse_uri(config.uri)
        uri_options = {key.lower(): value for key, value in parsed['options'].items()}
        expected = {'user': parsed['username'], 'db': uri_options['authsource']}
        if auth.get('authenticatedUsers', []) != [expected]:
            raise MongoConfigurationError('MONGO_AUTH_IDENTITY_REQUIRED')
        databases = client.admin.command('listDatabases', filter={'name': config.database},
                                        nameOnly=True, authorizedDatabases=True)['databases']
        if config.database not in {row['name'] for row in databases}:
            raise MongoConfigurationError('MONGO_DATABASE_NOT_QUALIFIED')
        # Shared application authentication needs users access. This also denies
        # a valid login with a role unrelated to application resources.
        client[config.database].users.find_one({'_id': '__luminar_readiness_never_written__'}, {'_id': 1}, max_time_ms=2000)
        with MongoClient(_deny_probe_uri(config.uri), serverSelectionTimeoutMS=3000,
                         connectTimeoutMS=3000, socketTimeoutMS=3000,
                         retryReads=False, retryWrites=False) as anonymous:
            try:
                anonymous[config.database]['__luminar_auth_gate__'].find_one(
                    {'_id': '__luminar_readiness_never_written__'}, {'_id': 1}, max_time_ms=2000)
            except OperationFailure as error:
                if error.code not in {13, 18}:
                    raise MongoConfigurationError('MONGO_AUTHORIZATION_NOT_VERIFIED') from None
            else:
                raise MongoConfigurationError('MONGO_AUTHORIZATION_NOT_ENFORCED')


def connect(config, **options):
    if not config.authenticated:
        return MongoClient(config.uri, **options)
    client = None
    try:
        bounds = {'serverSelectionTimeoutMS': 3000, 'connectTimeoutMS': 3000}
        bounds.update(options)
        client = MongoClient(config.uri, **bounds)
        _qualify(client, config)
        return client
    except Exception as error:
        if client is not None:
            client.close()
        if isinstance(error, MongoConfigurationError):
            raise
        raise MongoConfigurationError('MONGO_AUTH_CONNECTION_NOT_QUALIFIED') from None
