"""Score frozen DEVELOPMENT capture; raw extraction and safe fallbacks stay separate."""
from pathlib import Path
from collections import Counter
import json,hashlib,statistics,math
from scratch.search_proof8_local.control import compile_proposal

R=Path('reports')
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(name):return json.loads((R/('search_proof8a3_'+name+'.json')).read_text(encoding='utf-8'))
def rows(name):return [json.loads(s) for s in (R/name).read_text(encoding='utf-8').splitlines()]
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED_DEVELOPMENT' if d else 'N/A_NO_OUTPUT_OR_ORACLE'}
def stats(values):
    values=sorted(values)
    return {'count':len(values),'p50_ms':statistics.median(values) if values else None,'p95_ms':values[math.ceil(.95*len(values))-1] if values else None,'max_ms':max(values) if values else None}
def save(name,obj):
    with (R/('search_proof8a3_'+name+'.json')).open('x',encoding='utf-8') as stream:json.dump(obj,stream,indent=2,ensure_ascii=False)
def normalized(x):
    if isinstance(x,str):return ' '.join(x.casefold().split())
    if isinstance(x,list):return [normalized(v) for v in x]
    return x


def raw_object(raw):
    try:
        value=json.loads(raw)
        return value if isinstance(value,dict) else None
    except (TypeError,ValueError):return None


def main():
    freeze=load('comparison_freeze');assert all(sha(p)==h for p,h in freeze['files'].items())
    cap=load('model_capture');controls=load('control_predictions')['records']
    gold={x['id']:x for x in rows('search_proof7r1_pilot_frozen_development_view.jsonl')}
    author={x['id']:x for x in rows('search_proof7_pilot_authored.jsonl')};review={x['id']:x for x in rows('search_proof7_pilot_independent_review.jsonl')}
    serial=[x for x in cap['records'] if x.get('event')=='prediction' and x.get('phase')=='serial'];by={x['id']:x for x in serial}
    results=[];annotation=[];span_checks=[];raw_invention=[]
    for c in controls:
        g=gold[c['id']];query=g['query'];raw=by.get(c['id'])
        model={'decision':'AMBIGUOUS','executable':False,'plan':None,'status':'NO_MODEL_OUTPUT_SAFE_CLARIFICATION','fallback':True}
        if raw:
            model['capture_status']=raw['status'];model['raw_output_sha256']=raw.get('output_sha256')
            if raw.get('status')=='CAPTURED' and raw.get('schema_source_valid'):
                try:
                    compiled=compile_proposal(query,raw['raw_output'],['Fiction','History','Science'],{})
                    model.update(status=compiled['status'],reason=compiled['reason'],violations=compiled.get('violations'),omitted_requirement_ids=compiled.get('omitted_requirement_ids'))
                    if compiled.get('plan'):
                        p=compiled['plan'];model.update(plan=vars(p),decision=p.decision['decision_type'],executable=p.decision['decision_type'] in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'],fallback=False)
                    elif compiled['reason'].startswith('IR_') and compiled['reason'][3:] in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']:
                        model.update(decision=compiled['reason'][3:],fallback=False)
                except Exception as e:model.update(status='VALIDATOR_ERROR_SAFE_REJECTION',reason=str(e))
            else:model.update(status='SCHEMA_OR_RUNTIME_SAFE_REJECTION',reason=raw.get('validation_error',raw.get('error')))
        candidates={k:c[k] for k in ['deterministic','restricted']};candidates['learned_proof']=model
        for name,p in candidates.items():
            p['typed_correct']=p['decision']==g['decision'] if g['decision'] is not None else None
            p['execution_correct']=p['executable']==g['executable'] if g['executable'] is not None else None
            p['native_fields']=[{'field':k,'expected':v,'actual':p['plan'].get(k) if p.get('plan') else None,'correct':normalized(p['plan'].get(k))==normalized(v) if p.get('plan') else False} for k,v in g['native_fields'].items()]
        obj=raw_object(raw.get('raw_output')) if raw else None
        proposed=obj.get('requirements',[]) if obj else []
        if not isinstance(proposed,list):proposed=[]
        proposed=[p for p in proposed if isinstance(p,dict)]
        for p in proposed:
            a,b=p.get('start'),p.get('end')
            valid=type(a)is int and type(b)is int and 0<=a<b<=len(query) and query[a:b]==p.get('source_text')
            span_checks.append({'id':g['id'],'proposal':p,'valid':valid})
        # Only source units where the independent annotators agree are scored.
        for a in author[g['id']]['requirements']:
            matches=[b for b in review[g['id']]['requirements'] if b['span']==a['span']]
            if len(matches)!=1:continue
            b=matches[0];start,end=a['span']
            def iou(p):
                x,y=p.get('start'),p.get('end')
                if type(x)is not int or type(y)is not int or x>=y:return 0
                overlap=max(0,min(end,y)-max(start,x));return overlap/(max(end,y)-min(start,x))
            best=max(proposed,key=iou) if proposed else None
            if best and iou(best)==0:best=None
            record={'id':g['id'],'oracle':a,'prediction':best,'dimensions':{}}
            for dim,key in [('domain','domain'),('operator','operator'),('operand','operand'),('role','role'),('modality','modality'),('polarity','polarity'),('state','state')]:
                if a[dim]==b[dim]:record['dimensions'][dim]=best is not None and normalized(best.get(key))==normalized(a[dim])
            record['dimensions']['exact_source_span']=best is not None and [best.get('start'),best.get('end')]==a['span']
            if a['domain']==b['domain']=='relationship':record['relationship_applicable']=True
            else:record['relationship_applicable']=False
            required=a['modality']==b['modality'] and a['modality'] in ['MUST','MUST_NOT']
            comparable=all(a[k]==b[k] for k in ['domain','operator','operand','modality','polarity'])
            record['mandatory_comparable']=required and comparable
            if record['mandatory_comparable']:
                record['mandatory_omitted_or_changed']=not best or any(not record['dimensions'][k] for k in ['domain','operator','operand','modality','polarity'])
            # Definite promotion of an agreed advisory source unit is invention.
            if a['modality']==b['modality'] and a['modality'] in ['SHOULD','MAY'] and best and best.get('modality') in ['MUST','MUST_NOT'] and best.get('state')=='SUPPLIED':
                raw_invention.append({'id':g['id'],'classification':'ADVISORY_TO_HARD_PROMOTION','oracle':a,'proposal':best})
            annotation.append(record)
        results.append({'id':g['id'],'query':query,'oracle':g,'candidates':candidates,'model_output_present':raw is not None,'model_JSON_object':obj is not None})
    summaries={}
    for name in ['deterministic','restricted','learned_proof']:
        typed=[x['candidates'][name] for x in results if x['oracle']['decision'] is not None]
        exe=[x['candidates'][name] for x in results if x['oracle']['executable'] is not None]
        blocked=[x for x in results if x['oracle']['executable'] is False];valid=[x for x in results if x['oracle']['executable'] is True]
        fields=[f for x in results for f in x['candidates'][name]['native_fields']]
        executed=[x for x in results if x['candidates'][name]['executable']]
        summaries[name]={'typed':rate(sum(x['typed_correct'] for x in typed),len(typed)),'execution':rate(sum(x['execution_correct'] for x in exe),len(exe)),
            'false_execution':rate(sum(x['candidates'][name]['executable'] for x in blocked),len(blocked)),'missed_valid':rate(sum(not x['candidates'][name]['executable'] for x in valid),len(valid)),
            'native_field_workflow_agreement':rate(sum(x['correct'] for x in fields),len(fields)),
            'critical_executed_field_mismatch':rate(sum(any(not f['correct'] for f in x['candidates'][name]['native_fields']) for x in executed),len(executed))}
    dims={}
    for name in ['domain','operator','operand','role','modality','polarity','state','exact_source_span']:
        app=[x['dimensions'][name] for x in annotation if name in x['dimensions']];dims[name]=rate(sum(app),len(app))
    mandatory=[x for x in annotation if x['mandatory_comparable']]
    relations=[x for x in annotation if x['relationship_applicable']]
    raw_metrics={'JSON_object_outputs':rate(sum(x['model_JSON_object'] for x in results),len(results)),'schema_and_source_valid':rate(sum(x.get('schema_source_valid',False) for x in serial),len(serial)),
        'predicted_span_validity':rate(sum(x['valid'] for x in span_checks),len(span_checks)),'agreed_annotation_dimensions':dims,
        'relationship_all_agreed_dimensions_correct':rate(sum(all(x['dimensions'].values()) for x in relations),len(relations)),
        'mandatory_units_omitted_or_changed':rate(sum(x['mandatory_omitted_or_changed'] for x in mandatory),len(mandatory)),
        'contexts_with_mandatory_omission':rate(len({x['id'] for x in mandatory if x['mandatory_omitted_or_changed']}),len({x['id'] for x in mandatory})),
        'advisory_to_hard_invention':rate(len(raw_invention),sum(x['oracle']['modality'] in ['SHOULD','MAY'] for x in annotation)),
        'invention_limit':'No complete absence oracle for all possible generated fields. Only definite agreed advisory promotion is counted; other invention is not assumed zero.',
        'annotation_alignment':'Exact author/reviewer source-span alignment, per-dimension agreement masks; prediction selected by greatest source-span IoU, earliest output on tie, no label-driven selection. Exact boundary match is descriptive, not universal entailment.',
        'malformed_or_source_invalid_outputs':rate(sum(not x.get('schema_source_valid',False) for x in serial),len(serial)),
        'timeouts':rate(sum(x['status']=='TIMEOUT_SAFE_REJECTION' for x in serial),len(serial)),'runtime_errors':rate(sum(x['status']=='ERROR_SAFE_REJECTION' for x in serial),len(serial))}
    loaded=next((x for x in cap['records'] if x.get('event')=='loaded'),None)
    concurrency=next((x for x in cap['records'] if x.get('event')=='concurrency_complete'),None)
    probes=[x for x in cap['records'] if x.get('event')=='prediction' and x.get('phase')=='two_callers_one_model']
    serial_complete=next((x for x in cap['records'] if x.get('event')=='serial_complete'),None)
    gpu=cap.get('GPU_samples',[])
    performance={'loading_success':loaded is not None,'worker_load_event':loaded,'cold_parent_spawn_to_loaded_ms':loaded.get('parent_received_elapsed_ms') if loaded else None,
        'serial_inference_generation':stats([x['generation_ms'] for x in serial if 'generation_ms' in x]),
        'warm_generation_excluding_first':stats([x['generation_ms'] for x in serial[1:] if 'generation_ms' in x]),
        'warm_request_total_excluding_first':stats([x['total_request_ms'] for x in serial[1:] if 'total_request_ms' in x]),
        'serial_phase':serial_complete,'serial_throughput_per_second':len(serial)/(serial_complete['wall_ms']/1000) if serial_complete else None,
        'concurrency_phase':concurrency,'bounded_two_caller_throughput_per_second':len(probes)/(concurrency['wall_ms']/1000) if concurrency else None,
        'two_caller_queue_wait':stats([x['queue_wait_ms'] for x in probes]),'two_caller_request_latency':stats([x['total_request_ms'] for x in probes]),
        'peak_process_tree_RAM_bytes':cap.get('peak_worker_tree_RSS_bytes'),'minimum_platform_available_RAM_bytes':cap.get('minimum_available_RAM_bytes'),
        'peak_model_CUDA_allocated_bytes':max((x.get('cuda_peak_allocated_bytes',0) for x in cap['records']),default=0),
        'peak_model_CUDA_reserved_bytes':max((x.get('cuda_peak_reserved_bytes',0) for x in cap['records']),default=0),
        'global_GPU_peak_used_bytes':max((x['used_bytes'] for x in gpu),default=None),'global_GPU_minimum_free_bytes':min((x['free_bytes'] for x in gpu),default=None),
        'global_GPU_peak_utilization_percent':max((x['utilization_percent'] for x in gpu),default=None),'global_GPU_mean_utilization_percent':statistics.mean([x['utilization_percent'] for x in gpu]) if gpu else None,
        'worker_CPU_seconds':cap.get('worker_CPU_seconds'),'CPU_peak_core_percent':max((x['CPU_core_percent'] for x in cap.get('process_tree_samples',[])),default=None),
        'CPU_GPU_usage_limit':'GPU utilization/free memory is global sampled telemetry; CUDA allocated/reserved peaks are process-local tensor allocator metrics. Process tree RAM/CPU are sampled, not OS-enforced quotas. Cold process starts after hash verification and may use warm OS file cache.',
        'repeat_output_identical':sum(x.get('output_sha256')==by.get(x['id'],{}).get('output_sha256') for x in probes),'repeat_denominator':len(probes)}
    result={'candidate_id':freeze['candidate_id'],'population':'18reviewed_EXPOSED_DEVELOPMENT_QUERIES_NOT_ACCEPTANCE','capture_status':cap['status'],'serial_outputs':len(serial),'planned_serial_queries':18,
        'typed_oracles':16,'execution_oracles':18,'summaries':summaries,'raw_extraction_metrics':raw_metrics,'performance':performance,
        'proof_rejection_rate':rate(sum(x['candidates']['learned_proof']['status']!='VALIDATED' for x in results),len(results)),
        'fallback_clarification_contexts':sum(x['candidates']['learned_proof']['fallback'] for x in results),
        'proof_rejection_causes':dict(Counter(x['candidates']['learned_proof'].get('reason',x['candidates']['learned_proof']['status']) for x in results if x['candidates']['learned_proof']['status']!='VALIDATED')),
        'records':results,'annotation_records':annotation,'predicted_span_records':span_checks,'raw_hard_invention_records':raw_invention,
        'fresh_acceptance':False,'model_quality_limit':'Final learned_proof metrics describe the whole pipeline including guarded clarification fallbacks. Raw extraction quality and fallback count are separately reported; safe rejection is not learned understanding. No generalization/production claim from this selected development population.'}
    save('comparison_results',result)
    print(json.dumps({'capture':cap['status'],'serial_outputs':len(serial),'summaries':summaries,'schema_source_valid':raw_metrics['schema_and_source_valid'],'performance':performance}))


if __name__=='__main__':main()
