"""Fail-closed audience boundary for announcement reads and inbox navigation."""

def member_query(user_id):
    return {'$or': [
        {'audience':'ALL_ACTIVE_MEMBERS','recipient_user_id':None},
        {'audience':{'$exists':False},'recipient_user_id':None},
        {'audience':'SPECIFIC_MEMBER','recipient_user_id':{'$eq':user_id,'$type':['int','long']}}]}

def can_read(row,user_id):
    scope=row.get('audience','ALL_ACTIVE_MEMBERS');recipient=row.get('recipient_user_id')
    return (scope=='ALL_ACTIVE_MEMBERS' and recipient is None or
        scope=='SPECIFIC_MEMBER' and type(recipient) is int and recipient==user_id)
