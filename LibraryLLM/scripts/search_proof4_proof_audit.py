"""Native edit-boundary audit; pure schemas/functions, no Mongo imports."""
import json,ast
from pathlib import Path
from copy import deepcopy
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from fastapi import HTTPException
from scripts.search_v2c_c5er_offline_native import compile_functions
from scratch.search_proof_recovery_v4 import parser as p
def main():
    observations=[]
    plan=p.parse_query('category Fiction',['Fiction']);plan.author_text='invented'
    assert not p.executable(p.validate(p.decide(plan)))
    observations.append({'case':'decision reset preserves proof and rejects invented author','passed':True})
    assert not p.executable(p.validate(p.QueryPlan('books','SMART')))
    observations.append({'case':'SMART plan without proof cannot execute','passed':True})
    env={k:getattr(p,k) for k in ['parse_query','validate','decide','executable','normalize','FacetVocabulary']};env.update(deepcopy=deepcopy,HTTPException=HTTPException)
    transform=compile_functions('search/query_interaction.py',['transformer'],env)['transformer']
    for operation in ['correction_apply','correction_keep']:
        q='include category Fictoin';plan=p.parse_query(q,['Fiction'])
        try:r=transform({'query':q,'mode':'SMART','filters':{},'omit':[]},{'operation':operation,'correction':plan.corrections[0]},None)(plan,['Fiction'],{});status=200
        except HTTPException as e:status=e.status_code
        assert status==(200 if operation=='correction_apply' else 422)
        observations.append({'case':'actual native '+operation,'status':status,'integration_compatible':operation=='correction_apply'})
    source=Path('search/interaction_api.py');cls=next(n for n in ast.parse(source.read_text(encoding='utf8')).body if isinstance(n,ast.ClassDef) and n.name=='ChoiceRequest')
    env=dict(BaseModel=BaseModel,ConfigDict=ConfigDict,Field=Field,UUID=UUID,Mode=Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT'])
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),env)
    for length in [150,151,500]:
        try:env['ChoiceRequest'](query='x'*length,clarification_id=uuid4(),choice_id=uuid4());ok=True
        except ValidationError:ok=False
        assert ok==(length==150);observations.append({'case':'actual raw query schema','length':length,'accepted':ok})
    with Path('reports/search_proof4_edit_audit.json').open('x',encoding='utf8') as f:json.dump({'observations':observations,'assertions_passed':len(observations),'Mongo_calls':0,'full_native_choice_compatible':False,'limitation':'Legacy correction_keep removes a hard constraint without recompiling its source contract and is now rejected. Pure completion drafts do not implement durable one-use/CAS.'},f,indent=2)
    print(json.dumps({'checks':len(observations),'Mongo_calls':0}))
if __name__=='__main__':main()
