"""Finite pure mode/protocol diagnostics; no production imports or writes."""
import ast,json,hashlib
from pathlib import Path
from typing import Literal
from uuid import UUID,uuid4
from pydantic import BaseModel,Field,ConfigDict,ValidationError
from scratch.search_proof_recovery_v7 import parser

def main():
    R=Path('reports');caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf-8'))['scopes'];rows=[]
    for scope,c in caps.items():
        for q in ['by "Oak Vale"; rating at least 4','titled "online rated above 4"','by "Marsh"; exclude whole word "ar"']:
            for mode in ['SMART','EXACT']:
                p=parser.validate(parser.parse_query(q,c['subjects'],mode),c['capabilities'])
                assert parser.executable(p),(scope,q,mode,p.decision)
                if mode=='EXACT':assert p.exact_text==q and p.rating_min is None and not p.formats and not p.exclude_terms
                elif q.startswith('by "Marsh"'):assert p.exclude_terms==['ar'] and parser.matches(p,{'authors':['Marsh'],'title':'Harbor'})
                elif q.startswith('titled'):assert p.title_text=='online rated above 4' and not p.formats and p.rating_min is None
                else:assert p.author_text=='oak vale' and p.rating_min==4
                rows.append({'scope':scope,'mode':mode,'query':q,'passed':True})
    path=Path('search/interaction_api.py');source=path.read_text(encoding='utf-8');cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='ChoiceRequest')
    protocol=[]
    for label,bound in [('ACTIVE',150),('ISOLATED_WIDENING_PROPOSAL',500)]:
        node=ast.parse(ast.unparse(cls)).body[0]
        if bound==500:
            query=next(n for n in node.body if isinstance(n,ast.AnnAssign) and n.target.id=='query')
            next(k for k in query.value.keywords if k.arg=='max_length').value=ast.Constant(value=500)
        env=dict(BaseModel=BaseModel,ConfigDict=ConfigDict,Field=Field,UUID=UUID,Mode=Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT'])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(path),'exec'),env)
        for length in [150,151,500,501]:
            try:env['ChoiceRequest'](clarification_id=uuid4(),choice_id=uuid4(),query='x'*length);ok=True
            except ValidationError:ok=False
            assert ok==(length<=bound)
            protocol.append({'schema':label,'query_length':length,'accepted':ok})
    with (R/'search_proof7_mode_protocol_audit.json').open('x',encoding='utf-8') as f:json.dump({'mode_cases':rows,'mode_passed':len(rows),'protocol':protocol,'active_schema_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'production_schema_changed':False,'native_resolver_query_equality':'unchanged; widening only addresses transport length','Mongo_calls':0,'live_authorization_qualification':False},f,indent=2)
    print(json.dumps({'mode_checks':len(rows),'schema_checks':len(protocol),'Mongo_calls':0}))
if __name__=='__main__':main()
