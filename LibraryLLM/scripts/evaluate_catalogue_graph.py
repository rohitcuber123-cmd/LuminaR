"""KG3: frozen seeds, identical caller/exclusions/k, actual existing API comparison."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from knowledge_graph.core import CatalogueGraph,connect,public_book
from knowledge_graph.metrics import compare

def main():
    from backend.database.mongodb import users_collection,issues_collection,reservations_collection,reading_list_collection,recommendation_feedbacks_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    graph=CatalogueGraph();meta=graph.meta()
    output=ROOT/'reports/kg3_evaluation.json';seed_path=ROOT/'reports/kg3_seeds.json'
    if output.exists():raise FileExistsError('Refusing to overwrite KG3 evidence')
    user=next(u for u in users_collection.find({'role':'GENERAL_USER','is_email_verified':True}) if current_identity({'sub':str(u['user_id'])}))
    headers={'Authorization':'Bearer '+create_access_token(user['user_id'],user['email'],user['role'])}
    collections=[issues_collection,reservations_collection,reading_list_collection,recommendation_feedbacks_collection]
    def state():return [hashlib.sha256(json.dumps(list(c.find({})),sort_keys=True,default=str).encode()).hexdigest() for c in collections]
    before=state();seed_ids=[]
    with connect() as db:
        for number in range(32):
            row=db.execute('SELECT work_id FROM books WHERE id=?',(1+number*meta['books']//32,)).fetchone()
            if row:seed_ids.append((row['work_id'],'systematic full-catalogue interval'))
        for name,where in [('no authors',"authors='[]' AND subjects!='[]'"),('no subjects',"subjects='[]' AND authors!='[]'"),('isolated',"subjects='[]' AND authors='[]'")]:
            seed_ids.extend((row['work_id'],name) for row in db.execute('SELECT work_id FROM books WHERE '+where+' ORDER BY id LIMIT 2'))
    config=json.loads((ROOT/'reports/assistant_latency_cases.json').read_text())
    seed_ids.extend((wid,'existing seeded recommendation fixture') for wid in config['seeds'])
    seen=set();seeds=[]
    for wid,stratum in seed_ids:
        if wid not in seen:seeds.append(dict(work_id=wid,stratum=stratum,**{k:v for k,v in graph.book(wid).items() if k!='work_id'}));seen.add(wid)
    seed_path.write_text(json.dumps(seeds,indent=2),encoding='utf-8')
    result={'created_at':datetime.now(timezone.utc).isoformat(),'snapshot':meta,'k':10,'seeds':seeds,'runs':[],
        'method':'32 equally spaced books across all 5M snapshot positions, 2 each no-author/no-subject/isolated, plus existing recommendation seed fixtures; deduplicated before outcomes. One real verified reader, identical active loan/reservation exclusions, same k=10. No feedback or account writes.',
        'kg4_gate':{'candidate_conditions':{'seed_coverage_at_least':.90,'novel_candidate_seed_fraction_at_least':.50,'mean_diversity_decline_at_most':.05,'reason_path_validity':1.0},
                    'quality_condition':'Independent relevance labels or reader utility evidence are required; metadata overlap/diversity/coverage alone cannot satisfy this condition.'}}
    def save():output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    with httpx.Client(timeout=240) as client:
        for port in [8002,8003,8004]:
            client.get(f'http://127.0.0.1:{port}/health' if port!=8004 else f'http://127.0.0.1:{port}/').raise_for_status()
        # Search/model/metadata warm-up is separate from comparison rows.
        client.post('http://127.0.0.1:8004/recommendations/from-book',headers=headers,json={'work_id':seeds[0]['work_id'],'limit':10}).raise_for_status()
        for number,seed in enumerate(seeds,1):
            row={'work_id':seed['work_id'],'stratum':seed['stratum']}
            for name,url in [('existing','http://127.0.0.1:8004/recommendations/from-book'),('kg','http://127.0.0.1:8002/experimental/kg/more-like-this')]:
                started=time.perf_counter();response=client.post(url,headers=headers,json={'work_id':seed['work_id'],'limit':10});elapsed=(time.perf_counter()-started)*1000
                row[name+'_status']=response.status_code;row[name+'_ms']=elapsed
                if response.status_code!=200:row[name+'_error']=response.json();continue
                body=response.json();row[name]=[public_book(book) for book in body['recommendations']]
                if name=='kg':row['reason_paths']={book['work_id']:book['reason_paths'] for book in body['recommendations']};row['candidate_count']=body['candidate_count']
            if 'existing' in row and 'kg' in row:row['metrics']=compare(row['existing'],row['kg'])
            result['runs'].append(row);save()
            print(json.dumps({'seed':number,'of':len(seeds),'work_id':seed['work_id'],'existing_ms':row['existing_ms'],'kg_ms':row['kg_ms'],'overlap':row.get('metrics',{}).get('overlap_at_k')}),flush=True)
    successful=[r for r in result['runs'] if 'metrics' in r]
    def average(values):return statistics.mean(values) if values else None
    summary={}
    for name in ['existing','kg']:
        all_ids={b['work_id'] for row in successful for b in row[name]}
        summary[name]={'nonempty_seed_coverage':average([bool(row[name]) for row in successful]),
            'full_k_seed_coverage':average([len(row[name])==10 for row in successful]),'unique_recommended_books':len(all_ids),
            'catalogue_coverage':len(all_ids)/meta['books'],
            'mean_subject_diversity':average([row['metrics'][name+'_diversity']['subject_pairwise_distance'] for row in successful if row['metrics'][name+'_diversity']['subject_pairwise_distance'] is not None]),
            'latency_median_ms':statistics.median(row[name+'_ms'] for row in successful),'latency_max_ms':max(row[name+'_ms'] for row in successful)}
    summary['paired_seeds']=len(successful);summary['failed_seeds']=len(seeds)-len(successful)
    summary['mean_overlap_at_k']=average([r['metrics']['overlap_at_k'] for r in successful]);summary['mean_jaccard']=average([r['metrics']['jaccard'] for r in successful])
    summary['seeds_with_kg_only_candidates']=average([bool(r['metrics']['kg_only_ids']) for r in successful])
    paired_diversity=[r['metrics']['kg_diversity']['subject_pairwise_distance']-r['metrics']['existing_diversity']['subject_pairwise_distance']
                     for r in successful if r['metrics']['kg_diversity']['subject_pairwise_distance'] is not None and r['metrics']['existing_diversity']['subject_pairwise_distance'] is not None]
    summary['paired_diversity_seeds']=len(paired_diversity)
    summary['paired_subject_diversity_delta_mean']=average(paired_diversity)
    result['summary']=summary;result['real_state_unchanged']=before==state()
    result['kg4_decision']='DEFERRED: no independent relevance/reader-utility labels. Candidate novelty and metadata metrics cannot authorize a claim of improved recommendations. Existing production candidate/scoring pipeline remains unchanged.'
    save()
if __name__=='__main__':main()
