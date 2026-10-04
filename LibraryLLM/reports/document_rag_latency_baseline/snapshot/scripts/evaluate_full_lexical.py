"""Read-only full-sidecar validation and diagnostic measurements."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import psutil
from dotenv import load_dotenv
from pymongo import MongoClient
from scripts.measure_lexical_schemas import stats
from search.lexical_store import (LexicalSearchStore,FIRST_VALUE_SQL,NEXT_VALUE_SQL,
                                  EDIT_VALUE_SQL,digest_file,
                                  prefix_upper,search_with_lexical_diagnostics)
from search.typo_assistance import normalize_structured


def timed(fn,repeats=100):
    for _ in range(5): fn()
    samples=[]
    for _ in range(repeats):
        start=time.perf_counter(); fn()
        samples.append((time.perf_counter()-start)*1000)
    return stats(samples)


def steps(db,fn):
    counter=[0]
    def progress():
        counter[0]+=1
        return 0
    db.set_progress_handler(progress,1)
    try: fn()
    finally: db.set_progress_handler(None,0)
    return counter[0]


def semantic_state():
    root=ROOT/'datasets/ai/faiss/hnsw'
    pointer=json.loads((root/'active_index.json').read_text(encoding='utf-8'))
    m=json.loads((root/'versions'/pointer['version']/'manifest.json').read_text(encoding='utf-8'))
    with sqlite3.connect((root/'sync_queue.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        state,attempts=db.execute('SELECT state,attempts FROM status WHERE id=1').fetchone()
        latest=db.execute('SELECT max(seq) FROM events').fetchone()[0] or 0
    return {k:m[k] for k in ('semantic_generation','version','mapping_count','active_vectors','deleted_vectors')} | {
        'pending':latest>m['semantic_generation'],'retry_attempts':attempts,'index_status':state}


def verify_mongo(books,typ,value,work_ids):
    checked=0
    for wid in work_ids:
        doc=books.find_one({'work_id':wid},{'_id':0,'title':1,'authors':1})
        if doc is None: return {'valid':False,'checked':checked,'missing_work_id':wid}
        values=[doc.get('title')] if typ=='TITLE' else doc.get('authors') or []
        if isinstance(values,str): values=[values]
        if value not in {normalize_structured(x) for x in values if isinstance(x,str)}:
            return {'valid':False,'checked':checked,'mismatched_work_id':wid}
        checked+=1
    return {'valid':True,'checked':checked}


def sampled_entries(store,books,typ):
    count=store.manifest['title_relationship_count' if typ=='TITLE' else 'author_relationship_count']
    out=[]
    for fraction in (.00001,.02,.2,.4,.6,.8,.98,.99999):
        offset=min(count-1,int(count*fraction))
        row=store.db.execute('SELECT normalized_value,work_id FROM lexical_values '
                             'WHERE value_type=? ORDER BY normalized_value,work_id LIMIT 1 OFFSET ?',
                             (typ,offset)).fetchone()
        if row and verify_mongo(books,typ,row[0],[row[1]])['valid']:
            out.append({'fraction':fraction,'value':row[0],'work_id':row[1]})
    return out


def typo_variants(value,typ):
    positions=[i for i,c in enumerate(value[:8]) if c.isalpha() and c.isascii()]
    if not positions: return []
    i=positions[min(1,len(positions)-1)]
    variants=[('deletion',value[:i]+value[i+1:]),
              ('insertion',value[:i]+'x'+value[i:]),
              ('duplicate',value[:i]+value[i]+value[i:])]
    if i+1<len(value) and value[i+1].isascii() and value[i+1].isalpha() and value[i]!=value[i+1]:
        variants.append(('transposition',value[:i]+value[i+1]+value[i]+value[i+2:]))
    words=value.split(' ')
    if typ=='AUTHOR' and len(words)>1 and len(words[-1])>=5:
        pos=value.rfind(' ')+2
        variants.append(('surname_missing_character',value[:pos]+value[pos+1:]))
    if typ=='TITLE':
        long_word=next((w for w in words if len(w)>=6 and w[0].isalpha()),None)
        if long_word:
            pos=value.find(long_word)+min(3,len(long_word)-2)
            variants.append(('title_word_missing_character',value[:pos]+value[pos+1:]))
    return [(label,v) for label,v in variants if v!=value and len(v)>=5]


def full_typos(store,books):
    required=[('TITLE','frankenstien'),('AUTHOR','mary shelly'),
              ('AUTHOR','charls dickens'),('AUTHOR','george orwel')]
    results=[]
    for typ,q in required:
        r=store.fuzzy(typ,q)
        selected=r['match']['value'] if r['match'] else None
        ids=r['work_ids'] if selected else []
        results.append({'type':typ,'query':q,'candidate_count':len(r['candidates']),
                        'selected':selected,'score':r['match']['similarity'] if r['match'] else None,
                        'second_best_score':r['scores'][1][0] if len(r['scores'])>1 else None,
                        'margin':r['margin'],'reason':r['reason'],
                        'candidate_generation_seeks':r['candidate_generation_seeks'],
                        'candidate_probe_count':r['candidate_probe_count'],
                        'candidate_generation_ms':r['candidate_generation_ms'],
                        'fuzzy_scoring_ms':r['fuzzy_scoring_ms'],
                        'work_id_expansion_ms':r['work_id_expansion_ms'],
                        'selected_work_ids':ids,'total_lexical_ms':r['elapsed_ms'],
                        'candidate_vm_steps':steps(store.db,lambda:store.candidates(typ,q)),
                        'warm_timing_ms':timed(lambda:store.fuzzy(typ,q)),
                        'mongo_validation':verify_mongo(books,typ,selected,ids) if selected else None})
    return results


def expanded_typos(store,books,samples):
    cases=[]
    for typ in ('TITLE','AUTHOR'):
        for entry in samples[typ]:
            for label,query in typo_variants(entry['value'],typ):
                if store.exact(typ,query,1): continue
                r=store.fuzzy(typ,query)
                selected=r['match']['value'] if r['match'] else None
                ids=r['work_ids'] if selected else []
                cases.append({'type':typ,'category':label,'query':query,'expected':entry['value'],
                              'selected':selected,'reason':r['reason'],
                              'correct':selected==entry['value'] and entry['work_id'] in ids,
                              'candidate_count':len(r['candidates']),
                              'mongo_validation':verify_mongo(books,typ,selected,ids) if selected else None})
    return {'cases':cases,'total':len(cases),'correct':sum(x['correct'] for x in cases),
            'by_category':{label:{'total':sum(x['category']==label for x in cases),
                                  'correct':sum(x['category']==label and x['correct'] for x in cases)}
                           for label in sorted({x['category'] for x in cases})}}


def false_positives(store,samples):
    cases=[]
    for q in ('AI','it','C++','C#','1984','python','java','foundation'):
        cases.append(('required',q))
    for entry in samples['TITLE']:
        cases.append(('verified_exact',entry['value']))
        word=entry['value'].split(' ')[0]
        if len(word)>=5 and word!=entry['value'] and not store.exact('TITLE',word,1):
            cases.append(('valid_title_prefix',word))
    # Include many distinct current title values from spread positions without
    # loading the vocabulary into Python.
    count=store.manifest['title_relationship_count']
    for n in range(1,81):
        row=store.db.execute('SELECT normalized_value FROM lexical_values WHERE value_type=? '
                             'ORDER BY normalized_value,work_id LIMIT 1 OFFSET ?',
                             ('TITLE',int(count*n/81))).fetchone()
        if row:
            cases.append(('verified_exact',row[0]))
            word=row[0].split(' ')[0]
            if len(word)>=5 and word!=row[0] and not store.exact('TITLE',word,1):
                cases.append(('valid_title_prefix',word))
    seen=set(); results=[]
    for kind,q in cases:
        if (kind,q) in seen: continue
        seen.add((kind,q))
        r=store.fuzzy('TITLE',q)
        results.append({'kind':kind,'query':q,'selected':r['match']['value'] if r['match'] else None,
                        'reason':r['reason']})
    wrong=[r for r in results if r['selected']]
    return {'total':len(results),'fuzzy_selections':len(wrong),
            'incorrect_selection_rate':len(wrong)/len(results) if results else None,
            'cases':results}


def fallback(root,store):
    class SemanticStub:
        def search(self,q): return {'results':[{'work_id':'semantic_only'}]}
    engine=SemanticStub()
    result={'active':search_with_lexical_diagnostics(engine,store,'frankenstien')}
    with tempfile.TemporaryDirectory(prefix='lexical-fallback-',dir=root.parent) as directory:
        test=Path(directory)
        pointer={'version':store.manifest['sidecar_version'],'previous':None}
        (test/'active_lexical.json').write_text(json.dumps(pointer),encoding='utf-8')
        name='lexical_'+pointer['version']
        (test/(name+'.json')).write_text(json.dumps(store.manifest),encoding='utf-8')
        for scenario in ('missing_pointer','bad_pointer','missing_db','checksum_mismatch','unavailable_reader'):
            if scenario=='missing_pointer': (test/'active_lexical.json').unlink(missing_ok=True)
            else: (test/'active_lexical.json').write_text(json.dumps(pointer if scenario!='bad_pointer' else {'version':'bad'}),encoding='utf-8')
            if scenario in ('checksum_mismatch','unavailable_reader'):
                os.link(store.path,test/(name+'.sqlite'))
            if scenario=='checksum_mismatch':
                changed=dict(store.manifest,sha256='0'*64)
                (test/(name+'.json')).write_text(json.dumps(changed),encoding='utf-8')
            if scenario=='unavailable_reader':
                (test/(name+'.json')).write_text(json.dumps(store.manifest),encoding='utf-8')
            if scenario=='unavailable_reader':
                with patch('search.lexical_store.read_connection',side_effect=OSError('simulated')):
                    failed=LexicalSearchStore(test)
            else: failed=LexicalSearchStore(test)
            response=search_with_lexical_diagnostics(engine,failed,'frankenstien')
            result[scenario]={'lexical_available':failed.health()['lexical_available'],
                              'semantic_results_preserved':response.get('results')==[{'work_id':'semantic_only'}],
                              'error_type':(failed.health()['lexical_last_error'] or '').split(':')[0]}
            failed.close()
            (test/(name+'.sqlite')).unlink(missing_ok=True)
    result['active']={'lexical_available':result['active']['lexical_diagnostics']['health']['lexical_available'],
                      'diagnostics_operate':bool(result['active']['lexical_diagnostics']['title']['candidates'])}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root')
    parser.add_argument('--output',default='full_validation_distinct.json')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    root=Path(args.root or os.getenv('LUMINAR_LEXICAL_PATH',ROOT/'datasets/ai/lexical/published'))
    process=psutil.Process()
    before=process.memory_info().rss
    start=time.perf_counter()
    store=LexicalSearchStore(root,expected_source_db='luminar_library')
    startup=time.perf_counter()-start
    if not store.health()['lexical_available']: raise RuntimeError(store.health())
    opened=process.memory_info().rss
    m=store.manifest
    with MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017')) as client:
        books=client['luminar_library'].books
        samples={typ:sampled_entries(store,books,typ) for typ in ('TITLE','AUTHOR')}
        exact={}
        for typ in ('TITLE','AUTHOR'):
            measurements=[]
            for entry in samples[typ]:
                value=entry['value']
                measurements.append({'value':value,'fraction':entry['fraction'],
                                     'timing_ms':timed(lambda:store.exact(typ,value)),
                                     'work_id_timing_ms':timed(lambda:store.work_id(entry['work_id']))})
            exact[typ]=measurements
        queries=full_typos(store,books)
        expanded=expanded_typos(store,books,samples)
        negatives=false_positives(store,samples)
    warm=process.memory_info().rss
    for _ in range(100): store.fuzzy('AUTHOR','charls dickens')
    repeated=process.memory_info().rss
    plan={
        'first':store.db.execute('EXPLAIN QUERY PLAN '+FIRST_VALUE_SQL,
                                 ('TITLE','fran',prefix_upper('fran'))).fetchall(),
        'next':store.db.execute('EXPLAIN QUERY PLAN '+NEXT_VALUE_SQL,
                                ('TITLE','frankenstein',prefix_upper('fran'))).fetchall(),
        'edited_exact':store.db.execute('EXPLAIN QUERY PLAN '+EDIT_VALUE_SQL,
                                        ('TITLE','frankenstein')).fetchall(),
    }
    work={'normal_prefix':steps(store.db,lambda:store.candidates('TITLE','frankenstein')),
          'crowded_prefix':steps(store.db,lambda:store.candidates('AUTHOR','charles')),
          'typo_edit_probe':steps(store.db,lambda:store.candidates('AUTHOR','charls dickens'))}
    nulls=store.db.execute("SELECT sum(work_id IS NULL),sum(work_id=''),sum(normalized_value IS NULL),sum(normalized_value='') FROM lexical_values").fetchone()
    failures=fallback(root,store)
    output={'measured_at':datetime.now(timezone.utc).isoformat(),
            'manifest':m,'health':store.health(),'startup_seconds':startup,
            'startup_components_seconds':store.startup_timings,'integrity_check':'ok',
            'sha256_recomputed_matches':digest_file(store.path)==m['sha256'],
            'null_empty_counts':nulls,'query_plan':plan,'vm_steps':work,
            'reader_rss_before_bytes':before,'reader_rss_open_bytes':opened,
            'reader_rss_after_warm_bytes':warm,'reader_rss_after_repeated_typos_bytes':repeated,
            'sampled_verified_entries':samples,'exact_lookups':exact,
            'required_typos':queries,'expanded_typos':expanded,'false_positive_benchmark':negatives,
            'failure_fallback':failures,'semantic_state_after':semantic_state()}
    store.close()
    (root/args.output).write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'startup_seconds':startup,'row_count':m['row_count'],
                      'required_typos':queries,'expanded_typo_summary':{k:v for k,v in expanded.items() if k!='cases'},
                      'false_positive_summary':{k:v for k,v in negatives.items() if k!='cases'},
                      'vm_steps':work,'reader_rss_delta_bytes':opened-before,
                      'fallback':failures,'semantic_state_after':output['semantic_state_after']},indent=2))

if __name__=='__main__': main()
