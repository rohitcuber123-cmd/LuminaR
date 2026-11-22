"""New private notice visibility within the existing aggregated account inbox.

Existing generic lending history is intentionally unaffected. All collections
come from the caller's database, including disposable tests.
"""
from uuid import UUID
from backend.services.announcement_audience import member_query
KIND = 'ANNOUNCEMENT_PUBLISHED'

def eligible_libraries(database, user_id):
    user = database.users.find_one({'user_id':user_id}, {'_id':0,'role':1,'is_active':1,'is_email_verified':1,'password_setup_required':1})
    if not user or user.get('is_active',True) is not True or not user.get('is_email_verified') or user.get('password_setup_required') or user.get('role') not in ['ADMIN','LIBRARIAN','GENERAL_USER']:
        return []
    memberships = list(database.institution_memberships.find({'user_id':user_id,'status':'ACTIVE','role':{'$in':['ADMIN','LIBRARIAN','GENERAL_USER']}},
        {'library_id':1,'grant_invitation_id':1}))
    ids = [r['library_id'] for r in memberships]
    libraries = {r['library_id'] for r in database.institution_libraries.find({'library_id':{'$in':ids},'status':'ACTIVE'},{'library_id':1})}
    locked = {r['_id'] for r in database.institution_locks.find({'_id':{'$in':ids}},{'_id':1})}
    grants = [r['grant_invitation_id'] for r in memberships if r.get('grant_invitation_id')]
    proofs = {(r['library_id'],r['invitation_id']) for r in database.institution_invitations.find({'library_id':{'$in':ids},
        'invitation_id':{'$in':grants},'status':'ACCEPTED','accepted_by_user_id':user_id},{'library_id':1,'invitation_id':1})} if grants else set()
    return [r['library_id'] for r in memberships if r['library_id'] in libraries-locked and
        (not r.get('grant_invitation_id') or (r['library_id'],r['grant_invitation_id']) in proofs)]

def visible_query(database, user_id, query):
    # No notification scan across tenants and no recipient override from clients.
    return {'$and':[query, {'$or':[{'type':{'$ne':KIND}},
        {'type':KIND,'scope':'LIBRARY','library_id':{'$in':eligible_libraries(database,user_id)}}]}]}

def presentation_context(database, rows, user_id):
    """At most one query per collection per bounded inbox page, not per member."""
    identities=set()
    for row in rows:
        try:identities.add((str(UUID(row['library_id'])),str(UUID(row['source_id']))))
        except (ValueError,KeyError,TypeError):pass
    if not identities:return {},{},set()
    libraries=list({lib for lib,_ in identities})
    names={r['library_id']:r['name'] for r in database.institution_libraries.find({'library_id':{'$in':libraries},'status':'ACTIVE'},{'library_id':1,'name':1})}
    roles={r['library_id']:r['role'] for r in database.institution_memberships.find({'library_id':{'$in':libraries},'user_id':user_id,'status':'ACTIVE'},{'library_id':1,'role':1})}
    published={(r['library_id'],r['announcement_id']) for r in database.institution_announcements.find({
        '$and':[{'$or':[{'library_id':lib,'announcement_id':identity} for lib,identity in identities]},member_query(user_id)],'status':'PUBLISHED'}, {'library_id':1,'announcement_id':1})}
    return names,roles,published

def present(database, row, user_id, context=None):
    """Reconstruct a safe route from canonical source identity and current state."""
    row = dict(row)
    row.update(action_route=None, action_unavailable='Announcement unavailable or withdrawn')
    try:
        library_id = str(UUID(row['library_id'])); announcement_id = str(UUID(row['source_id']))
        if row.get('audience')!='MEMBER' or row.get('source_type')!='announcement': return row
        names,roles,published = context if context is not None else presentation_context(database,[row],user_id)
        row['library_name'] = names.get(library_id,'Library unavailable')
        if library_id in names and (library_id,announcement_id) in published:
            prefix = 'staff/' if roles.get(library_id) in ['ADMIN','LIBRARIAN'] else ''
            row.update(action_route=f'/{prefix}libraries/{library_id}/announcements/{announcement_id}',action_unavailable=None)
        else:
            row.update(message='This announcement is no longer available.')
    except (ValueError,KeyError,TypeError): pass
    # Copies deliberately carry only a generic message, never private body text.
    row['source_ref'] = {'announcement_id':row.get('source_id')}
    return row
