"""Fresh-library provisioning and conservative, explicit empty-legacy promotion.

Uses the existing durable circulation journal and V1 tenant gate. Historical
cutover/migration writers remain authoritative for libraries with legacy data.
"""
from uuid import NAMESPACE_URL, uuid5
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.institution_dependencies import actor_id
from backend.services.institution_repository import collection, library_mutation, audit
from backend.services.library_inventory_access import require_library_staff
from backend.services import library_lending_journal as journal
from backend.services import library_lending_service as lending
from backend.services.library_fee_service import initial_policy


def _effects(library_id, user_id, origin):
    policy = initial_policy(library_id, user_id)
    policy['provenance'] = 'Canonical library default: INR 5/day, UTC calendar day, charge stops at physical receipt.'
    effects = []
    for name, values in [('lending_config', {'state': 'CANONICAL'}),
                         ('v2c_config', {'state': 'CANONICAL', 'reservation_mode': 'CANONICAL', 'fee_mode': 'CANONICAL'})]:
        existing = collection(name).find_one({'library_id': library_id})
        effects.append(journal.effect(name, {'library_id': library_id},
            {'library_id': library_id, **values, 'initialization_origin': origin, 'cutover_at': lending.now()}, not bool(existing)))
    effects.append(journal.effect('fee_policies', {'library_id': library_id, 'policy_id': policy['policy_id']}, policy, True))
    return effects


def verify_initialized(library_id):
    a = collection('lending_config').find_one({'library_id': library_id}) or {}
    b = collection('v2c_config').find_one({'library_id': library_id}) or {}
    policy = collection('fee_policies').find_one({'library_id': library_id, 'version': 1})
    if a.get('state') != 'CANONICAL' or any(b.get(k) != 'CANONICAL' for k in ['state', 'reservation_mode', 'fee_mode']) or not policy:
        raise journal.RecoveryRequired('Library provisioning is incomplete; recover the durable plan before activation.')


def initialize_new(library_id, user_id):
    """Called only inside registration's PROVISIONING gate, before ACTIVE."""
    library = collection('libraries').find_one({'library_id': library_id, 'status': 'PROVISIONING', 'owner_user_id': user_id})
    if not library or collection('library_aliases').find_one({'canonical_library_id': library_id}):
        raise journal.RecoveryRequired('New-library provisioning provenance is invalid.')
    if any(collection(n).find_one({'library_id': library_id}) for n in ['lending_config', 'v2c_config', 'fee_policies']):
        raise journal.RecoveryRequired('Unexpected existing configuration requires provisioning recovery.')
    key = str(uuid5(NAMESPACE_URL, 'luminar-new-library:' + library_id))
    journal.commit(library_id, user_id, key, 'LIBRARY_CANONICAL_INITIALIZED', {},
                   _effects(library_id, user_id, 'NEW_LIBRARY'), {'library_id': library_id, 'state': 'CANONICAL'})
    verify_initialized(library_id)


def preflight(library_id):
    """Read-only, under a tenant gate when used to authorize promotion."""
    reasons = []
    scope = {'library_id': library_id}
    aliases = list(collection('library_aliases').find({'$or': [{'canonical_library_id': library_id}, {'legacy_library_id': library_id}]}))
    library = collection('libraries').find_one(scope) or {}
    if aliases or any(library.get(k) for k in ['legacy_library_id', 'legacy_alias', 'migration_source']):
        reasons.append('Explicit legacy association requires the existing migration procedure.')
    for name in ['migrations', 'inventory_migrations', 'v2c_migrations']:
        if collection(name).find_one({'$or': [scope, {'canonical_library_id': library_id}]}):
            reasons.append('Migration provenance exists: ' + name)
    for name, label in [('library_inventory', 'Mapped legacy inventory'), ('issues', 'Legacy loan history'),
                        ('reservations', 'Legacy reservation history'), ('fines', 'Legacy fee history')]:
        if db[name].find_one(scope):
            reasons.append(label + ' requires explicit reconciliation.')
    issue_ids = db.issues.distinct('issue_id', scope)
    if issue_ids and db.fines.find_one({'issue_id': {'$in': issue_ids}}):
        reasons.append('Legacy fees linked through issue history require reconciliation.')
    # This deliberately conservative path is for a truly empty installation.
    # It is never inferred from the usable catalogue count alone.
    for name in ['library_books', 'holdings', 'copies', 'lending_requests', 'loans', 'reservations', 'fees', 'fee_policies']:
        if collection(name).find_one(scope):
            reasons.append('Canonical history/state is not empty: ' + name)
    for name in ['lending_config', 'v2c_config']:
        config = collection(name).find_one(scope)
        if config and config.get('state') != 'LEGACY':
            reasons.append('Conflicting subsystem state: ' + name)
    if collection('lending_operations').find_one(scope) or collection('inventory_imports').find_one({**scope, 'status': {'$in': ['APPLYING', 'RECOVERY_REQUIRED']}}):
        reasons.append('Existing cutover or incomplete mutation requires its recovery procedure.')
    return {'library_id': library_id, 'safe': not reasons, 'reasons': reasons,
            'policy': 'Only truly empty, unassociated LEGACY libraries may use this promotion path.'}


def promotion_preflight(library_id, actor):
    _, member = require_library_staff(library_id, actor)
    if member['role'] != 'ADMIN':
        raise HTTPException(403, 'Library admin authority is required.')
    with library_mutation(library_id, durable=True):
        require_library_staff(library_id, actor, locked=True)
        return preflight(library_id)


def promote_empty(library_id, actor, command):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        _, member = require_library_staff(library_id, actor, locked=True)
        if member['role'] != 'ADMIN':
            raise HTTPException(403, 'Library admin authority is required.')
        user = actor_id(actor); payload = command.model_dump(mode='json')
        old = journal.receipt(library_id, user, command.idempotency_key, 'EMPTY_LIBRARY_CANONICAL_INITIALIZED', payload)
        if old is not None:
            return old
        report = preflight(library_id)
        if not report['safe']:
            raise HTTPException(409, detail=report)
        result = journal.commit(library_id, user, command.idempotency_key, 'EMPTY_LIBRARY_CANONICAL_INITIALIZED', payload,
            _effects(library_id, user, 'VERIFIED_EMPTY_LEGACY'), {'library_id': library_id, 'state': 'CANONICAL', 'preflight': report})
        verify_initialized(library_id)
        return result


def recover_initialization(library_id, *, writers_stopped=False):
    """Operator recovery, never online lock expiry or automatic promotion."""
    if not writers_stopped:
        raise ValueError('Stop all API/worker writers before recovering an uncertain initialization.')
    library = collection('libraries').find_one({'library_id': library_id})
    plans = list(collection('lending_operations').find({'library_id': library_id}).sort('created_at', 1))
    origins = {'LIBRARY_CANONICAL_INITIALIZED', 'EMPTY_LIBRARY_CANONICAL_INITIALIZED'}
    if not library or not collection('locks').find_one({'_id': library_id}) or not plans or any(p['operation_type'] not in origins for p in plans):
        raise ValueError('Initialization provenance and retained gate must be proven; use existing recovery for other operations.')
    for plan in plans:
        if plan['state'] != 'COMMITTED':
            journal.replay(plan)
    # A journal failure marks lending RECOVERY_REQUIRED; its validated plan is
    # the proof authorizing this absolute restoration, never a guessed state.
    journal.durable('lending_config').update_one({'library_id': library_id}, {'$set': {'state': 'CANONICAL'}})
    verify_initialized(library_id)
    if library['status'] == 'PROVISIONING':
        owner = library['owner_user_id']
        if not collection('security').find_one({'library_id': library_id}) or not collection('memberships').find_one({'library_id': library_id, 'user_id': owner, 'role': 'ADMIN', 'status': 'ACTIVE'}):
            raise ValueError('Registration security and owner authority are incomplete; do not activate.')
        audit(library_id, 'LIBRARY_REGISTERED', owner, event_id='registration:' + library_id)
        journal.durable('libraries').update_one({'library_id': library_id, 'status': 'PROVISIONING'}, {'$set': {'status': 'ACTIVE'}})
    journal.durable('locks').delete_one({'_id': library_id})
    return {'library_id': library_id, 'state': 'CANONICAL', 'recovered': True}
