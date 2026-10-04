"""Bounded shuffled GooAQ selection, frozen pairs, and broad answer pool."""
import argparse
from collections import Counter,defaultdict
import os
import random
import shutil
from gooaq_g3_controls import *
os.environ['HF_HOME']=str(CACHE)
os.environ['HF_DATASETS_CACHE']=str(CACHE/'datasets')
from datasets import load_dataset
import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rows',type=int,default=50000);ap.add_argument('--seed',type=int,default=42);ap.add_argument('--pool',type=int,default=200000);args=ap.parse_args()
    assert args.rows==50000 and args.seed==42 and args.pool==200000
    verify()
    if (DATA/'source_manifest.json').exists():raise FileExistsError('Frozen G3 pair selection already exists')
    if shutil.disk_usage(ROOT).free<5*1024**3:raise OSError('Insufficient disk headroom; STOP')
    probe=read(TRAIN/'reports/rag_g3_gooaq_source_probe.json');assert probe['status']=='accessible'
    schema=probe['schemas']['pair']['features'];assert schema=={'question':'string','answer':'string'}
    stream=load_dataset(probe['dataset_id'],'pair',split='train',revision=probe['revision'],streaming=True)
    if {c:stream.features[c].dtype for c in stream.features}!=schema:raise ValueError('Live source schema changed; STOP')
    stream=stream.shuffle(seed=42,buffer_size=10000)
    stats=Counter();records=[];seen_pairs=set();seen_queries=set();selected=[];corpus={}
    for row in stream:
        stats['rows_inspected']+=1
        q,p=row['question'],row['answer']
        if not q or not q.strip():stats['empty_questions']+=1
        if not p or not p.strip():stats['empty_answers']+=1
        if not q or not q.strip() or not p or not p.strip():continue
        q,p=q.strip(),p.strip();qn,pn=norm(q),norm(p)
        records.append({'source_record_id':stats['rows_inspected']-1,'question':q,'positive':p})
        if qn==pn:stats['question_equals_answer']+=1;continue
        corpus.setdefault(pn,{'positive':p,'source_record_id':stats['rows_inspected']-1})
        if (q,p) in seen_pairs:stats['exact_duplicate_pairs']+=1;continue
        seen_pairs.add((q,p))
        if len(selected)<50000 and qn not in seen_queries:
            selected.append({'question':q,'positive':corpus[pn]['positive']});seen_queries.add(qn)
        if len(selected)==50000 and len(corpus)>=200000:break
        if stats['rows_inspected']>500000:raise RuntimeError('Bounded 500k source cap exceeded; STOP')
        if stats['rows_inspected']%25000==0:print(f"inspected {stats['rows_inspected']}; pairs {len(selected)}; unique passages {len(corpus)}",flush=True)
    if len(selected)!=50000 or len(corpus)<200000:raise RuntimeError('Insufficient bounded source data; STOP')
    random.Random(42).shuffle(selected);train,val=selected[:45000],selected[45000:]
    assert not {norm(x['question']) for x in train}&{norm(x['question']) for x in val}
    qs=Counter(norm(x['question']) for x in records);answers=Counter(norm(x['positive']) for x in records)
    known=defaultdict(set)
    for x in records:known[norm(x['question'])].add(norm(x['positive']))
    stats['duplicate_normalized_questions']=sum(v-1 for v in qs.values());stats['duplicate_answer_passages']=sum(v-1 for v in answers.values())
    stats['multi_positive_questions']=sum(len(v)>1 for v in known.values())
    tokenizer=AutoTokenizer.from_pretrained(str(local_base_model()),local_files_only=True)
    token_stats={'inspected_usable':{'question':lengths(tokenizer,[x['question'] for x in records]),'answer':lengths(tokenizer,[x['positive'] for x in records])},
                 'selected_50000':{'question':lengths(tokenizer,[x['question'] for x in selected]),'answer':lengths(tokenizer,[x['positive'] for x in selected])}}
    DATA.mkdir(parents=True,exist_ok=True);files={}
    for name,rows in [('pairs_train',train),('pairs_validation',val),('source_records',records),('answer_corpus',list(corpus.values()))]:
        path=DATA/f'gooaq_g3_{name}.parquet';pq.write_table(pa.Table.from_pylist(rows),path,compression='zstd');files[name]={'path':str(path),'rows':len(rows),'sha256':sha(path)}
    manifest={'experiment':'G3_GOOAQ','dataset_id':probe['dataset_id'],'config':'pair','revision':probe['revision'],'split':'train','schema':schema,'source_row_count':probe['schemas']['pair']['splits']['train']['rows'],
              'automatic_download':'successful bounded streaming; no complete multi-million-row materialization','cache':str(CACHE),'selection':{'seed':42,'shuffle_buffer':10000,'pair_rule':'first 50k usable distinct normalized queries from seeded shuffled stream; seed-42 final shuffle, 45k/5k split; no later replacements','pool_rule':'continue same shuffled stream until at least 200k normalized unique answers; bounded cap 500k processed source records','buffer_note':'rows_inspected counts yielded rows; up to 10k lookahead rows may be internally buffered'},
              'inventory':dict(stats),'rows_materialized':len(records),'selected_rows':50000,'train_validation_normalized_query_overlap':0,'token_lengths':token_stats,'mining_corpus_count':len(corpus),
              'known_positive_scope':'all alternate positives discoverable among bounded inspected source records; unknown positives outside this pool remain unlabelled','answer_canonicalization':'first-seen original passage for normalized-equivalent texts; selected positives use that canonical source passage','files':files,'versions':read(TRAIN/'reports/rag_g3_gooaq_preflight.json')['versions']}
    write(DATA/'source_manifest.json',manifest);print(__import__('json').dumps(manifest,indent=2),flush=True)
if __name__=='__main__':main()
