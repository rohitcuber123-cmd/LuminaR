"""Local Mongo-authenticated read boundary. No application imports or grants.

This module deliberately never imports backend.database.mongodb: that module
creates an index on import. Application JWTs and Platform roles are irrelevant
to infrastructure authentication. Provisioning is outside the diagnostic CLI.
"""
import re
import time

from pymongo import MongoClient, timeout
from pymongo.uri_parser import parse_uri


class DiagnosticError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


COLLECTIONS = {
    'jobs': 'institution_intelligence_jobs',
    'targets': 'institution_intelligence_targets',
    'generations': 'institution_intelligence_generations',
    'locks': 'institution_locks',
}


class OperatorReader:
    """Authenticated reader exposing only bounded read operations."""
    def __init__(self, client, database, deadline):
        self.client, self.database, self.deadline = client, client[database], deadline
        self.operations = []
        self.authenticated = False
        with timeout(self.remaining()):
            auth = client[database].command('connectionStatus', showPrivileges=False).get('authInfo', {})
        users, roles = auth.get('authenticatedUsers', []), auth.get('authenticatedUserRoles', [])
        if (len(users) != 1 or users[0].get('db') != database or not users[0].get('user')
                or not roles or any(r != {'role': 'read', 'db': database} for r in roles)):
            raise DiagnosticError('OPERATOR_READ_PRINCIPAL_REQUIRED')
        self.authenticated = True

    def remaining(self):
        left = self.deadline-time.monotonic()
        if left <= 0:
            raise DiagnosticError('DIAGNOSTIC_DEADLINE')
        return left

    def _collection(self, name):
        if not self.authenticated or name not in COLLECTIONS:
            raise DiagnosticError('OPERATOR_AUTH_REQUIRED')
        self.remaining()
        return self.database[COLLECTIONS[name]]

    def rows(self, name, query, projection, *, sort=None, limit=1, hint=None):
        if type(limit) is not int or not 1 <= limit <= 201:
            raise DiagnosticError('INVALID_LIMIT')
        coll = self._collection(name)
        self.operations.append({'collection': name, 'operation': 'find', 'limit': limit})
        with timeout(self.remaining()):
            cursor = coll.find(query, projection).max_time_ms(min(1000, max(1, int(self.remaining()*1000)))).limit(limit)
            if sort:
                cursor = cursor.sort(sort)
            if hint:
                cursor = cursor.hint(hint)
            return list(cursor)

    def aggregate(self, name, pipeline):
        coll = self._collection(name)
        self.operations.append({'collection': name, 'operation': 'aggregate'})
        with timeout(self.remaining()):
            return list(coll.aggregate(pipeline, maxTimeMS=min(1000, max(1, int(self.remaining()*1000))), allowDiskUse=False))

    def close(self):
        self.client.close()


def connect_operator(uri, database='luminar_library', *, seconds=10):
    """Require explicit local SCRAM credentials, never anonymous/app defaults."""
    if (not isinstance(uri, str) or not uri or not isinstance(database, str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', database)
            or type(seconds) not in (int, float) or not 1 <= seconds <= 30):
        raise DiagnosticError('OPERATOR_AUTH_REQUIRED')
    try:
        if not uri.startswith('mongodb://'):
            raise ValueError()
        parsed = parse_uri(uri, validate=True)
        if (not parsed['username'] or not parsed['password'] or parsed['database'] != database
                or len(parsed['nodelist']) != 1 or parsed['nodelist'][0][0] not in ('127.0.0.1', 'localhost', '::1')
                or parsed['options'].get('authsource', database) != database
                or parsed['options'].get('authmechanism', 'SCRAM-SHA-256') not in ('SCRAM-SHA-256', 'SCRAM-SHA-1')):
            raise ValueError()
    except Exception:
        raise DiagnosticError('LOCAL_OPERATOR_CREDENTIAL_REQUIRED') from None
    client = None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=min(3000, int(seconds*1000)),
                             connectTimeoutMS=2000, socketTimeoutMS=3000, retryReads=False,
                             appname='LuminaR-operator-read-only')
        return OperatorReader(client, database, time.monotonic()+seconds)
    except DiagnosticError:
        if client:
            client.close()
        raise
    except Exception:
        if client:
            client.close()
        raise DiagnosticError('OPERATOR_AUTH_UNAVAILABLE') from None
