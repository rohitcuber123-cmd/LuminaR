"""Single independent acceptance scoring; no parser calls or gold amendments."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from copy import deepcopy
import hashlib,json,sys
from scripts.search_v2c_c5c_score import KINDS,OPERANDS,LISTS,rate,summarize
from scripts.search_v2c_c_evaluate import norm
from scripts.search_v2c_c4_evaluate import normalize_both
R=Path('reports');P='search_v2c_c5e_independent_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def main():
    config=load(R/(P+'parser_configuration.json'));freeze=load(R/'search_v2c_c5e_candidate_freeze.json')
    assert all(sha(p)==h for p,h in freeze['files'].items())
    complete=load(R/(P+'prediction_complete.json'));predpath=R/(P+'predictions.jsonl')
    assert sha(predpath)==complete['prediction_sha256']
    assert complete['parser_calls']==config['prediction_calls_planned'] and complete['retries']==0 and not complete['isolation_denials']
    population=Path(config['gold_population_path']);assert sha(population)==config['gold_population_sha256']
    write('scoring_started.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'predictions_sha256':sha(predpath),'gold_access_after_completed_capture':True,'parser_calls':0})
    def prohibit(frame,event,arg):
        if event=='call' and frame.f_code.co_name=='parse_query':raise RuntimeError('No parser calls during scoring')
    sys.setprofile(prohibit)
    gold={x['case_id']:x for x in rows(population)};pred=rows(predpath)
    assert len(gold)==len(pred)==90 and set(gold)=={p['case_id'] for p in pred}
    scored=[];fields=defaultdict(list);unadapted=[];provenance=[]
    for p in pred:
        g=gold[p['case_id']];actual=p.get('actual_plan',{});valid=p['status']=='CAPTURED' and p.get('typed_decision') in KINDS and type(p.get('executable')) is bool
        masks=g['metric_applicability'];hard=g['expected_hard_constraints'];assertions=[];mismatches={};excluded={}
        def assertion(field,wanted,observed,partial=False):
            good=set(norm(wanted)).issubset(set(norm(observed))) if partial and isinstance(wanted,list) and isinstance(observed,list) else norm(wanted)==norm(observed)
            assertions.append({'field':field,'expected':wanted,'actual':observed,'correct':good,'partial':partial});fields[field].append(good)
            if not good:mismatches[field]={'expected':wanted,'actual':observed}
        if valid:
            normalized_actual=normalize_both(deepcopy(actual));normalized_hard=normalize_both(deepcopy(hard))
            for field in sorted(OPERANDS):
                mask=masks.get(field,{})
                state=mask.get('status') if isinstance(mask,dict) else mask
                if state not in ['APPLICABLE','APPLICABLE_ABSENCE','PARTIALLY_APPLICABLE']:
                    excluded[field]=mask or {'status':'NO_GOLD_FIELD'};continue
                if state=='APPLICABLE_ABSENCE':wanted=[] if field in LISTS else False if field.endswith('_exclusive') else None
                else:
                    assert field in hard or 'resolved_value' in mask,(g['case_id'],field)
                    wanted=mask.get('resolved_value',normalized_hard.get(field))
                assertion(field,wanted,normalized_actual.get(field),state=='PARTIALLY_APPLICABLE')
            semantic_mask=masks.get('semantic_remainder',{})
            if (semantic_mask.get('status') if isinstance(semantic_mask,dict) else semantic_mask)=='APPLICABLE':
                assertion('semantic_text',g.get('expected_semantic_remainder',''),actual.get('semantic_text') or '')
            else:excluded['semantic_text']=semantic_mask
            sort=g.get('expected_sort');sort_mask=masks.get('sort',{})
            if isinstance(sort,str) and sort in ['RELEVANCE','RATING','NEWEST','TITLE']:
                assertion('sort',sort,actual.get('sort'))
            elif sort is not None:excluded['sort']={'status':'NO_ESTABLISHED_ADAPTER','gold_preserved':sort}
            q=g['query_text'];notices=actual.get('decision',{}).get('repair_notices',[])
            verified=[]
            for notice in notices:
                span=notice.get('source_span');good=isinstance(span,list) and len(span)==2 and 0<=span[0]<span[1]<=len(q) and q[span[0]:span[1]]==notice.get('from') and bool(notice.get('to'))
                verified.append(good)
            provenance.append({'case_id':g['case_id'],'notice_count':len(notices),'valid_source_provenance':sum(verified),'all_valid':all(verified)})
            if g['expected_typed_decision']=='EXECUTABLE_WITH_NOTICE':assertion('repair_notice_present',True,bool(notices))
            if notices:assertion('repair_notice_source_provenance',True,all(verified))
            if p['typed_decision']!=g['expected_typed_decision']:mismatches['decision']={'expected':g['expected_typed_decision'],'actual':p['typed_decision']}
            if p['executable'] is not g['expected_executable']:mismatches['execution_allowed']={'expected':g['expected_executable'],'actual':p['executable']}
        else:mismatches['invalid_output']={'status':p['status'],'error':p.get('error')}
        for a in g.get('expected_unadapted_author_assertions',[]):unadapted.append({'case_id':g['case_id'],'assertion':a,'status':'PRESERVED_UNADAPTED_NOT_SCORED'})
        row={'case_id':g['case_id'],'scope':g['scope_type'],'workspace':g['workspace_type'],'stratum':g['decision_stratum'],
             'shared_semantic_pattern_id':g.get('shared_semantic_pattern_id'),'valid_output':valid,'expected_decision':g['expected_typed_decision'],
             'decision':p.get('typed_decision'),'expected_execution':g['expected_executable'],'execution':p.get('executable'),
             'typed_correct':p.get('typed_decision')==g['expected_typed_decision'],'execution_correct':p.get('executable') is g['expected_executable'],
             'policy':p.get('assessment',{}).get('policy'),'all_scored_dimensions_correct':valid and not mismatches,'mismatches':mismatches,
             'assertions':assertions,'scoring_excluded_fields':excluded,'input_query_sha256':hashlib.sha256(g['query_text'].encode()).hexdigest()}
        scored.append(row)
    sys.setprofile(None)
    with (R/(P+'scored_observations.jsonl')).open('x',encoding='utf8') as f:
        for x in scored:f.write(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n')
    summary=summarize(scored)
    cells=[{'scope':scope,'stratum':stratum,**summarize([x for x in scored if x['scope']==scope and x['stratum']==stratum])}
           for scope in sorted({x['scope'] for x in scored}) for stratum in sorted({x['stratum'] for x in scored})]
    write('metrics.json',{'population':'C independent normative acceptance; 90 contexts, shared patterns explicitly grouped','overall':summary,'30_scope_stratum_cells':cells,
          'per_field':{k:rate(sum(v),len(v)) for k,v in sorted(fields.items())},'source_provenance':provenance,'unadapted_assertions':unadapted,
          'structured_advisory_accuracy':{'status':'N/A','reason':'No established structured-object to display-string oracle'},
          'scope_actor_accuracy':{'status':'N/A','reason':'Supplied context, not parser predictions'},
          'finite_sample_only':True,'norm_source':'Unchanged C5 norm and C4 formats-only BOTH expansion; no new fuzzy/equivalence scoring',
          'gold_sha256':sha(population),'predictions_sha256':sha(predpath),'scorer_sha256':sha(__file__),'parser_calls_in_scoring':0,
          'critical_execution_failures':[x['case_id'] for x in scored if x['expected_execution'] is False and x['execution'] is True]})
    write('failures.json',{'rows':[x for x in scored if x['mismatches']],'all_failures_retained':True,'no_candidate_revision_or_retest':True,
          'classification':'Wrong/absent/hallucinated scalar operands are functional fidelity failures under frozen field masks. Semantic remainder strings are strict representation diagnostics pending semantic review; no equivalence invented.'})
    write('scoring_complete.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'scored':len(scored),'parser_calls':0,'metrics_sha256':sha(R/(P+'metrics.json'))})
    print(json.dumps({'typed':summary['typed_accuracy'],'execution':summary['execution_accuracy'],'false_execution':summary['false_execution_count'],'missed_execution':summary['missed_execution_count'],'strict':summary['strict_scored_dimension_match']}))
if __name__=='__main__':main()
