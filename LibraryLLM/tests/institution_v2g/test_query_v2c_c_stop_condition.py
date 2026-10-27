"""V2C-C mandatory stop: denied workspace must preserve an allowed workspace."""
from copy import deepcopy
from uuid import uuid4
from search.query_execution import tenant_search
from search.session_store import collection
from test_query_v2a import query_library
from test_query_v2c_b import ACTOR,interaction_client


def test_staff_denial_must_not_delete_active_patron_context(query_library,database):
 lid,_,_,worker,_,_=query_library;sid=str(uuid4());api=interaction_client(database,worker)
 tenant_search(worker,lid,ACTOR,'books about neural networks',session_id=sid)
 before=deepcopy(collection().find_one({'_id':sid}));q='include Romance but exclude Romance'
 r=tenant_search(worker,lid,ACTOR,q,session_id=sid);cid=r['interpretation']['clarification']['clarification_id']
 pending=deepcopy(collection().find_one({'_id':'clarification:'+cid}))
 response=api.get('/query/suggestions',params={'q':'neur','library_id':lid,'staff':'true'})
 assert response.status_code==403
 membership=database.institution_memberships.find_one({'library_id':lid,'user_id':2})
 assert membership['status']=='ACTIVE' and membership['role']=='GENERAL_USER'
 assert collection().find_one({'_id':sid})==before,'A denied STAFF request deleted the still-authorized PATRON context'
 assert collection().find_one({'_id':pending['_id']})==pending
