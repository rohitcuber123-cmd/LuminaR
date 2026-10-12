"""Bounded current identity decoration for already authorized tenant audit pages.

Canonical events are never updated. No arbitrary account lookup API is exposed.
"""
from fastapi import HTTPException
from backend.database.mongodb import users_collection


def hydrate_activity_identities(library_id, rows):
    if len(rows) > 100 or any(row.get('library_id') != library_id for row in rows):
        raise HTTPException(404, 'Library resource not found.')
    ids = {row.get(field) for row in rows for field in ('actor_user_id', 'target_user_id')
           if type(row.get(field)) is int and row[field] > 0}
    identities = {}
    if ids:
        for user in users_collection.find({'user_id': {'$in': sorted(ids)}},
                                         {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1}).limit(len(ids)):
            identities[user['user_id']] = {
                'user_id': user['user_id'],
                'display_name': str(user.get('name') or '')[:200] or None,
                'email': str(user.get('email') or '')[:320] or None,
                'identity_source': 'CURRENT_ACCOUNT',
            }

    def identity(row, field):
        user_id = row.get(field)
        if user_id in identities:
            return identities[user_id]
        # Invitation audit already stores this safe event-time email snapshot.
        snapshot = row.get('target_email_normalized') if field == 'target_user_id' else None
        if snapshot:
            return {'user_id': user_id, 'display_name': None, 'email': str(snapshot)[:320],
                    'identity_source': 'EVENT_SNAPSHOT'}
        return None

    return [{**row, 'actor': identity(row, 'actor_user_id'),
             'member': identity(row, 'target_user_id')} for row in rows]
