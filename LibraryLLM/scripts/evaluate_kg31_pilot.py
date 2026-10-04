"""Compare graph ontologies on the SAME frozen pilot population and 40 seeds."""
from collections import Counter
import argparse
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from knowledge_graph.core import CatalogueGraph, canonical, terms
from knowledge_graph.metrics import compare
from knowledge_graph.topics import description_hash


def average(values):return statistics.mean(values) if values else None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--v2',type=Path,default=ROOT/'knowledge_graph/data/kg31_pilot_v2.sqlite');parser.add_argument('--report',type=Path,default=ROOT/'reports/kg_v1_vs_v2.json');args=parser.parse_args()
    report=args.report
    assert not report.exists()
    build=json.loads((ROOT/'reports/kg31_pilot_build.json').read_text())
    seeds=json.loads((ROOT/'reports/kg3_seeds.json').read_text())
    graphs={'v1':CatalogueGraph(ROOT/'knowledge_graph/data/kg31_pilot_v1.sqlite'),'v2':CatalogueGraph(args.v2)}
    build['v2']=graphs['v2'].meta();build['v2']['database_bytes']=args.v2.stat().st_size
    rows=[];needed={seed['work_id'] for seed in seeds}
    for graph in graphs.values():graph.more_like_this(seeds[0]['work_id'])
    for seed in seeds:
        row={'work_id':seed['work_id'],'title':seed['title'],'stratum':seed['stratum']}
        for name,graph in graphs.items():
            timings=[]
            for _ in range(3):
                started=time.perf_counter();result=graph.more_like_this(seed['work_id']);timings.append((time.perf_counter()-started)*1000)
            row[name]=result;row[name+'_timings_ms']=timings
            needed.update(book['work_id'] for book in result['recommendations'])
        row['metrics']=compare(row['v1']['recommendations'],row['v2']['recommendations'])
        rows.append(row)
    source={}
    with (ROOT/'reports/kg31_pilot_books.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            book=json.loads(line)
            if book['work_id'] in needed:source[book['work_id']]=book
    examples=[];path_count=0
    summaries={}
    for name in ['v1','v2']:
        ids=set();shares=[];same_author=[];types=[];reasons=[];generic=[];strong=[];topic_only=0
        for row in rows:
            seed=source[row['work_id']];seed_authors=set(terms(seed.get('authors')))
            books=row[name]['recommendations'];ids.update(book['work_id'] for book in books)
            same_author.append(sum(bool(seed_authors&set(terms(book['authors']))) for book in books)/len(books) if books else None)
            for book in books:
                contribution=Counter()
                assert math.isclose(sum(path['contribution'] for path in book['reason_paths']),book['score'])
                kinds={path['kind'] for path in book['reason_paths']}
                types.append(len(kinds));reasons.append(len(book['reason_paths']))
                strong.append(bool(kinds&{'author','subject','topic'}))
                topic_only+=kinds=={'topic'}
                for path in book['reason_paths']:
                    path_count+=1;contribution[path['kind']]+=path['contribution']
                    generic.append(path['catalogue_degree']/build['sample_books']>=.01)
                    assert path['nodes'][0]==row['work_id'] and path['nodes'][2]==book['work_id']
                    for evidence in path['provenance']:
                        raw=source[evidence['work_id']].get(evidence['field'])
                        if path['kind']=='topic':
                            assert evidence['description_sha256']==description_hash(raw)
                            assert canonical(evidence['value']) in canonical(raw)
                        else:assert canonical(evidence['value']) in terms(raw)
                shares.append({kind:contribution[kind]/book['score'] for kind in ['author','subject','topic']})
                if name=='v2' and 'topic' in kinds:
                    examples.append({'seed_work_id':row['work_id'],'seed_title':row['title'],'candidate_work_id':book['work_id'],
                                     'candidate_title':book['title'],'topic_only':kinds=={'topic'},
                                     'topics':[path['label'] for path in book['reason_paths'] if path['kind']=='topic'],
                                     'seed_excerpt':str(seed.get('description') or '')[:400],
                                     'candidate_excerpt':str(source[book['work_id']].get('description') or '')[:400]})
        timings=[time for row in rows for time in row[name+'_timings_ms']]
        summaries[name]={'seed_coverage':sum(bool(row[name]['recommendations']) for row in rows)/len(rows),
            'top10_completeness':sum(len(row[name]['recommendations'])==10 for row in rows)/len(rows),
            'unique_candidates':len(ids),'candidate_count_mean':average([row[name]['candidate_count'] for row in rows]),
            'mean_subject_diversity':average([row['metrics'][('existing' if name=='v1' else 'kg')+'_diversity']['subject_pairwise_distance'] for row in rows if row['metrics'][('existing' if name=='v1' else 'kg')+'_diversity']['subject_pairwise_distance'] is not None]),
            'same_seed_author_concentration_mean':average([value for value in same_author if value is not None]),
            'relationship_type_diversity_mean':average(types),'reason_count_mean':average(reasons),
            'generic_reason_fraction_degree_at_least_1_percent':average(generic),
            'strong_or_moderate_reason_fraction':average(strong),'topic_only_recommendations':topic_only,
            'mean_contribution_share':{kind:average([share[kind] for share in shares]) for kind in ['author','subject','topic']},
            'latency_median_ms':statistics.median(timings),'latency_p95_ms':sorted(timings)[math.ceil(.95*len(timings))-1],
            'latency_max_ms':max(timings)}
    differences=[row['metrics']['kg_diversity']['subject_pairwise_distance']-row['metrics']['existing_diversity']['subject_pairwise_distance'] for row in rows if row['metrics']['kg_diversity']['subject_pairwise_distance'] is not None and row['metrics']['existing_diversity']['subject_pairwise_distance'] is not None]
    scale=5_000_000/build['sample_books'];new_bytes=build['v2']['database_bytes']*scale
    estimate={'linear_projected_topic_nodes':build['v2']['features']['topic']*scale,
              'linear_projected_new_edges':(build['v2']['edges']-build['v1']['edges'])*scale,
              'linear_projected_disk_bytes':new_bytes,'conservative_peak_additional_bytes':new_bytes*3,
              'linear_projected_enrichment_seconds':build['v2'].get('total_enrichment_seconds_including_compaction',build['v2']['build_seconds'])*scale,
              'disk_free_now_bytes':shutil.disk_usage(ROOT).free,
              'limitation':'Linear projections from 100K; corpus degree, vocabulary growth and indexing can scale nonlinearly. Preserve V1 and allow 3x V2 output for staging/compaction.'}
    result={'population':'100040 systematic pilot works including all 40 frozen KG3 seeds; V1 and V2 have the same books. This is NOT full-5M V1 versus a small V2.',
            'seeds':seeds,'build':build,'rows':rows,'summary':summaries,'mean_top10_overlap':average([row['metrics']['overlap_at_k'] for row in rows]),
            'paired_diversity_seed_count':len(differences),'paired_diversity_delta_mean':average(differences),
            'verified_paths':path_count,'topic_examples':examples,'full_build_estimate':estimate,
            'full_build_gate':'PENDING source-reason review; no automatic full build or runtime switch.'}
    report.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['summary','mean_top10_overlap','paired_diversity_delta_mean','verified_paths','full_build_estimate']}),flush=True)
    print(json.dumps(examples,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
