"""V6 exposed development, one shared ontology, original gold unchanged."""
from pathlib import Path
from dataclasses import asdict
from uuid import uuid5,NAMESPACE_DNS
import json,sys,hashlib,time
from scratch.search_proof_recovery_v8 import parser
from scratch.search_proof_recovery_v8.completion import BoundContext
from scratch.search_proof_recovery_v8.contract import digest
from scratch.search_proof_recovery_v8.native_adapter import issue_choice,resolve_choice,ChoiceRequest500
from scratch.search_proof_recovery_v8.measurement import score_roles,completion_oracle
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score,summary


def main():
    tag=sys.argv[1];assert tag.isalnum();r=Path('reports');prefix='search_combined8_'+tag+'_v6_exposed_'
    gold=[json.loads(s) for s in (r/'search_proof6_reviewed_population.jsonl').read_text(encoding='utf-8').splitlines()]
    caps=json.loads((r/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf-8'))['scopes']
    snapshot=Path('scratch/search_combined8_history')/('v6_'+tag);snapshot.mkdir(parents=True)
    hashes={}
    for path in Path('scratch/search_proof_recovery_v8').glob('*.py'):
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest();(snapshot/(path.name+'.txt')).write_bytes(path.read_bytes())
    predictions=[];scored=[];roles=[];actions=[]
    for g in gold:
        c=caps[g['scope_type']];st=time.perf_counter();p=parser.validate(parser.parse_query(g['query_text'],c['subjects'],g['search_mode']),c['capabilities'])
        pred={'case_id':g['case_id'],'status':'CAPTURED','typed_decision':p.decision['decision_type'],'executable':parser.executable(p),'actual_plan':asdict(p),'assessment':parser.assess(p),'elapsed_ms':(time.perf_counter()-st)*1000}
        predictions.append(pred);scored.append(score(g,pred))
        roles.extend({'case_id':g['case_id'],**x} for x in score_roles(g['query_text'],g['expected_source_roles'],pred['actual_plan']['decision']['query_ir_contract']['requirements']))
        if not g.get('completion_input'):continue
        local=g['scope_type']!='GLOBAL';lid=str(uuid5(NAMESPACE_DNS,g['scope_type'])) if local else None
        ctx=BoundContext('offline-owner','offline-login',lid,g['workspace_type'],parser.PARSER_VERSION,'SMART',digest(p.raw_query),7,1000)
        inp=g['completion_input']
        try:
            issued=issue_choice(p,ctx,'complete',inp['field'])
            req=ChoiceRequest500(clarification_id=issued.clarification_id,choice_id=issued.choice_id,query=p.raw_query,library_id=lid,staff=ctx.workspace=='STAFF',value=inp['value'])
            draft=resolve_choice(req,issued,p,ctx,now=10,facets=c['subjects'],capabilities=c['capabilities'],authorized=True);n=draft['plan']
            out={'status':'CAPTURED','typed_decision':n.decision['decision_type'],'executable':parser.executable(n),'actual_plan':asdict(n),'assessment':parser.assess(n),'query':draft['query']}
        except Exception as e:out={'status':'REJECTED','error':str(e),'error_type':type(e).__name__}
        actions.append({'case_id':g['case_id'],'input_field':inp['field'],'prediction':out,'scored':score(completion_oracle(g),out),'commit_performed':False})
    applicable=[x for x in roles if x['applicable']]
    report={'population':'EXPOSED_V6_DEVELOPMENT_ONLY','candidate_id':parser.PARSER_VERSION,'fresh_acceptance':False,'gold_edited':False,'source_hashes':hashes,'summary':summary(scored),'scored':scored,
        'source_roles':{'correct':sum(x['role_correct'] for x in applicable),'modality_correct':sum(x['modality_correct'] for x in applicable),'denominator':len(applicable),'excluded':len(roles)-len(applicable),'records':roles},
        'native_completion':{'contexts':len(actions),'typed_correct':sum(x['scored']['typed_correct'] for x in actions),'execution_correct':sum(x['scored']['execution_correct'] for x in actions),'strict_correct':sum(x['scored']['all_scored_dimensions_correct'] for x in actions),'records':actions,'oracle_accessor':'expected_completion.sort preserved, independently audited; no gold edit','Mongo_CAS_verified':False}}
    with (r/(prefix+'predictions.jsonl')).open('x',encoding='utf-8') as f:
        for p in predictions:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    with (r/(prefix+'results.json')).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    print(json.dumps({'summary':report['summary'],'roles':{k:v for k,v in report['source_roles'].items() if k!='records'},'completion':{k:v for k,v in report['native_completion'].items() if k!='records'}}))


if __name__=='__main__':main()
