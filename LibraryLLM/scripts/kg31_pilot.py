"""Freeze a systematic 100K catalogue pilot plus the 40 original KG3 seeds."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.build_catalogue_graph import build
from scripts.build_kg_topics import enrich


def main():
    from backend.database.mongodb import books_collection
    seeds=json.loads((ROOT/'reports/kg3_seeds.json').read_text())
    path=ROOT/'reports/kg31_pilot_books.jsonl'
    assert not path.exists()
    started=time.perf_counter();count=0
    projection={'_id':0,'book_id':1,'work_id':1,'title':1,'authors':1,'subjects':1,'description':1,'active':1,'is_active':1,'searchable':1}
    with path.open('w',encoding='utf-8') as stream:
        for row in books_collection.find({'$or':[{'book_id':{'$mod':[50,0]}},{'work_id':{'$in':[s['work_id'] for s in seeds]}}]},projection).batch_size(2000):
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1
    def rows():
        with path.open(encoding='utf-8') as stream:
            for line in stream:yield json.loads(line)
    v1_path=ROOT/'knowledge_graph/data/kg31_pilot_v1.sqlite'
    v2_path=ROOT/'knowledge_graph/data/kg31_pilot_v2.sqlite'
    v1=build(rows(),v1_path,count)
    v1['scope']='systematic pilot, every 50th catalogue book_id plus frozen 40 seeds'
    v2=enrich(v1_path,v2_path,rows,scope=v1['scope'])
    report={'sample_books':count,'selection':v1['scope'],'frozen_source':str(path),
        'v1':v1,'v1_bytes':v1_path.stat().st_size,'v2':v2,
        'total_seconds':time.perf_counter()-started,
        'full_build_gate':{'integrity_required':True,'strong_source_reason_review_required':True,
            'median_query_seconds_at_most':1,'maximum_query_seconds_at_most':5,
            'maximum_mean_paired_diversity_decline':.05,'maximum_topic_contribution_share':.5,
            'estimated_build_seconds_at_most':3600,'minimum_free_disk_after_estimated_peak_gb':15}}
    (ROOT/'reports/kg31_pilot_build.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
