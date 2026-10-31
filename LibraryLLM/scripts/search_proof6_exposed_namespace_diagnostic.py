"""POST-PRIMARY EXPOSED DEVELOPMENT diagnostic. Never a fresh acceptance rerun.

Primary source, gold, capture and scorer stay byte-frozen. This diagnoses an
unregistered native-field/IR-domain alignment; it cannot replace primary gates.
"""
from pathlib import Path
from uuid import uuid5,NAMESPACE_DNS
import json,hashlib
from scratch.search_proof_recovery_v6 import parser
from scratch.search_proof_recovery_v6.proposals import FAMILIES
from scratch.search_proof_recovery_v6.contract import digest
from scratch.search_proof_recovery_v6.completion import BoundContext
from scratch.search_proof_recovery_v6.native_adapter import issue_choice,ChoiceRequest500,resolve_choice
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score

def main():
    R=Path('reports');P='search_proof6_'
    read=lambda n:[json.loads(s) for s in (R/(P+n)).read_text(encoding='utf-8').splitlines()]
    gold=read('reviewed_population.jsonl');pred={x['case_id']:x for x in read('independent_predictions.jsonl')}
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf-8'))['scopes']
    aliases={name:f for f,columns in FAMILIES.items() for name in columns};aliases.update(soft_preferences='preference',background='context')
    roles=[];actions=[]
    for g in gold:
        pp=pred[g['case_id']];rr=pp['actual_plan']['decision'].get('query_ir_contract',{}).get('requirements',[])
        for o in g.get('expected_source_roles',[]):
            text=o.get('source_text',o.get('text',''));field=o.get('field');domain=aliases.get(field,field if field in FAMILIES else None)
            if not domain or not text or g['query_text'].count(text)!=1:
                roles.append({'case_id':g['case_id'],'applicable':False,'oracle':o,'reason':'No registered/unambiguous native scalar alias or unique span'});continue
            a=g['query_text'].index(text);b=a+len(text)
            match=[r for r in rr if r['field']==domain and (r['source_span'][0]<=a<b<=r['source_span'][1] or a<=r['source_span'][0]<r['source_span'][1]<=b)]
            actual_roles=sorted({r['source_role'] for r in match});actual_modal=sorted({r['modality'] for r in match})
            roles.append({'case_id':g['case_id'],'applicable':True,'oracle':o,'IR_domain':domain,'role_correct':actual_roles==[o['role']],
                'modality_correct':actual_modal==[o['modality']],'actual_roles':actual_roles,'actual_modalities':actual_modal})
        if not g.get('completion_input'):continue
        inp=g['completion_input'];domain=aliases.get(inp['field'],inp['field']);c=caps[g['scope_type']]
        p=parser.validate(parser.parse_query(g['query_text'],c['subjects'],g['search_mode']),c['capabilities'])
        local=g['scope_type']!='GLOBAL';lid=str(uuid5(NAMESPACE_DNS,g['scope_type'])) if local else None
        ctx=BoundContext('offline-owner','offline-login',lid,g['workspace_type'],parser.PARSER_VERSION,'SMART',digest(p.raw_query),7,1000)
        try:
            i=issue_choice(p,ctx,'complete',domain)
            request=ChoiceRequest500(clarification_id=i.clarification_id,choice_id=i.choice_id,query=p.raw_query,library_id=lid,staff=ctx.workspace=='STAFF',value=inp['value'])
            d=resolve_choice(request,i,p,ctx,now=10,facets=c['subjects'],capabilities=c['capabilities'],authorized=True);n=d['plan']
            result={'status':'CAPTURED','actual_plan':vars(n),'typed_decision':n.decision['decision_type'],'executable':parser.executable(n),'assessment':parser.assess(n),'query':d['query']}
        except Exception as e:result={'status':'REJECTED','error_type':type(e).__name__,'error':str(e),'detail':getattr(e,'detail',None)}
        o=g['expected_completion'];decision=o['decision'];gg={'case_id':g['case_id']+':mapped-completion','scope_type':g['scope_type'],'decision_stratum':decision,'expected_typed_decision':decision,'expected_executable':decision in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'],'expected_hard_constraints':o['hard_constraints'],'metric_applicability':o['metric_applicability'],'expected_sort':o.get('expected_sort','RELEVANCE'),'expected_semantic_remainder':o.get('expected_semantic_remainder')}
        actions.append({'case_id':g['case_id'],'input_field':inp['field'],'mapped_IR_domain':domain,'prediction':result,'scored':score(gg,result),'commit_performed':False})
    app=[r for r in roles if r['applicable']]
    report={'population':'EXPOSED_AFTER_FAILED_PRIMARY; POST_HOC_DIAGNOSTIC_ONLY','fresh_independent_acceptance':False,'candidate_or_gold_changed':False,'primary_attempts_still':1,
        'role_correct':sum(r['role_correct'] for r in app),'modality_correct':sum(r['modality_correct'] for r in app),'role_denominator':len(app),'role_excluded':len(roles)-len(app),
        'completion_contexts':len(actions),'completion_typed_correct':sum(a['scored']['typed_correct'] for a in actions),'completion_execution_correct':sum(a['scored']['execution_correct'] for a in actions),
        'completion_strict_correct':sum(a['scored']['all_scored_dimensions_correct'] for a in actions),'role_records':roles,'completion_records':actions,'Mongo_calls':0,'actual_authentication_or_CAS':False}
    with (R/(P+'exposed_namespace_diagnostic.json')).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ['role_records','completion_records']}))
if __name__=='__main__':main()
