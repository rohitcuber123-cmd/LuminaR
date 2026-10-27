"""Real Mongo multi-turn state safety, using the existing isolated fixture."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json,os
import pytest
from search.query_execution import tenant_search
from search.session_store import collection,clear
from test_query_v2a import query_library
from test_query_v2c_b import ACTOR,interaction_client

@pytest.mark.parametrize('minimum',[0,1,2,3,4])
def test_v2cc_sequence_reject_resolve_refine_clear_and_scope_safety(query_library,database,minimum):
 lid,_,_,worker,_,_=query_library;sid=str(uuid4());api=interaction_client(database,worker);observed=[]
 def turn(q,expected,accepted=True):
  before=deepcopy(collection().find_one({'_id':sid}));r=tenant_search(worker,lid,ACTOR,q,session_id=sid)
  after=collection().find_one({'_id':sid});kind=r['interpretation']['decision']['decision_type'];assert kind==expected
  if not accepted:assert after==before
  observed.append({'query':q,'decision':kind,'accepted_unchanged':after==before,'plan':after['current_plan'] if after else None,'version':after['version'] if after else None})
  return r
 turn('books about neural networks','EXECUTABLE');p=collection().find_one({'_id':sid});assert p['current_plan']['semantic_text']=='neural networks'
 turn('only online','EXECUTABLE');p=collection().find_one({'_id':sid});assert p['current_plan']['formats']==['ONLINE'] and p['current_plan']['semantic_text']=='neural networks'
 turn('rating above '+str(minimum),'EXECUTABLE');p=collection().find_one({'_id':sid});assert p['current_plan']['rating_min']==minimum and p['current_plan']['formats']==['ONLINE']
 turn('fiction 4','AMBIGUOUS',False)
 turn('mystery under 250 pages','UNSUPPORTED',False)
 rejected=turn('include Romance but exclude Romance','CONTRADICTORY',False);c=rejected['interpretation']['clarification'];before=deepcopy(collection().find_one({'_id':sid}))
 body={'clarification_id':c['clarification_id'],'choice_id':str(uuid4()),'query':'include Romance but exclude Romance','library_id':lid,'session_id':sid}
 assert api.post('/query/resolve',json=body).status_code==404 and collection().find_one({'_id':sid})==before
 body['choice_id']=c['candidate_choices'][0]['choice_id'];assert api.post('/query/resolve',json=body).status_code==200
 resolved=collection().find_one({'_id':sid});assert resolved['version']==before['version']+1 and resolved['current_plan']['subjects']==['Romance']
 assert api.post('/query/resolve',json=body).status_code==409 and collection().find_one({'_id':sid})==resolved
 turn('deep learning instead','EXECUTABLE');p=collection().find_one({'_id':sid});assert p['current_plan']['subjects']==['Deep learning']
 clear(sid,ACTOR,lid);assert collection().find_one({'_id':sid}) is None
 turn('books about planets','EXECUTABLE');before=deepcopy(collection().find_one({'_id':sid}))
 from fastapi import HTTPException
 with pytest.raises(HTTPException):tenant_search(worker,lid,{'sub':'2','sid':'another-login'},'books about stars',session_id=sid)
 assert collection().find_one({'_id':sid})==before
 database.institution_memberships.update_one({'library_id':lid,'user_id':2},{'$set':{'status':'REMOVED'}})
 with pytest.raises(HTTPException):tenant_search(worker,lid,ACTOR,'books about planets',session_id=sid)
 assert collection().find_one({'_id':sid}) is None
 path=Path(__file__).resolve().parents[2]/'reports'/os.getenv('LUMINAR_SEARCH_SESSION_REPORT','search_v2c_c_session_sequences.json');data=json.loads(path.read_text()) if path.exists() else []
 data.append({'case_id':'sequence-rating-'+str(minimum),'database':database.name,'turns':observed,'forged_unchanged':True,'resolution_single_commit':True,'duplicate_unchanged':True,'cross_sid_unchanged':True,'clear_verified':True,'revocation_invalidated':True,'corruption_events':0})
 path.write_text(json.dumps(data,indent=2,default=str))
