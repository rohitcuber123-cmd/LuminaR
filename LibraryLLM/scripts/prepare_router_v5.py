"""Ordered contract freeze and independent evaluation construction, no training."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
DATA = ROOT / 'evaluation/assistant_router_v5'
from assistant.router_v5.contracts import registry, meanings_hash, registry_hash, POSITIONS, FIELDS, CRITERIA
from router_v5_data import sealed_manual, independent_generation_tasks, row


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8') as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def norm(text):
    return ' '.join(''.join(c.lower() if c.isalnum() else ' ' for c in text).split())


def freeze_contracts():
    if (ROOT / 'reports/assistant_router_v5_contract_meanings_seal.json').exists():
        raise SystemExit('Meanings already frozen; preserve the existing experiment.')
    old = []
    for name in ['existing', 'hidden']:
        old += json.loads((ROOT / f'reports/assistant_router_v3_baseline_snapshot/{name}_sealed.json').read_text(encoding='utf8'))
    old_text = {norm(r['message']) for r in old}
    copied = [t for c in registry() for t in c['examples'] if norm(t) in old_text]
    if copied:
        raise ValueError('Contract exemplars copy old regression sentences: ' + repr(copied))
    content = {'contracts':registry(),'positions':POSITIONS,'fields':FIELDS,'criteria':CRITERIA,
               'meanings_sha256':meanings_hash(),'registry_sha256':registry_hash(), 'old_frozen_verbatim_exemplars':0}
    write_new(ROOT / 'reports/assistant_router_v5_contracts.json',content)
    write_new(ROOT / 'reports/assistant_router_v5_contract_meanings_seal.json',
              {'created_at':datetime.now(timezone.utc).isoformat(),'meanings_sha256':meanings_hash(),
               'registry_sha256':registry_hash(), 'order':'Contract meanings fixed before V5 evaluation creation; DEV does not exist yet.'})
    print('CONTRACTS FROZEN',len(content['contracts']),flush=True)


def manual():
    assert (ROOT / 'reports/assistant_router_v5_contract_meanings_seal.json').exists()
    write_new(DATA/'sealed_manual.json',sealed_manual())
    print('INDEPENDENT MANUAL EVAL',len(sealed_manual()),flush=True)


def generate():
    if (ROOT / 'reports/assistant_router_v5_sealed_manifest.json').exists():
        raise SystemExit('Evaluation already sealed; do not regenerate.')
    assert (DATA/'sealed_manual.json').exists()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from rag.llm import LuminaRLLM
    torch.manual_seed(1251)
    path=DATA/'independent_qwen_raw.jsonl'
    done={r['task']:r for r in map(json.loads,path.read_text(encoding='utf8').splitlines())} if path.exists() else {}
    model=LuminaRLLM()
    for i,(key,scenario,_,_) in enumerate(independent_generation_tasks()):
        if i in done:
            continue
        prompt=('Write four independent natural-language questions a library member might ask in this scenario. '
                'Vary one casual fragment, one indirect question, one ordinary short question and one detailed request. '
                'Keep exactly the scenario meaning. No added constraints, book names, ordinal positions or transactions. '
                'Do not answer or classify. No examples are supplied. Output only JSON {"texts":[four strings]}. Scenario: '+scenario)
        tokens=model.tokenizer.apply_chat_template([{'role':'system','content':'You write evaluation requests, not answers.'},
                 {'role':'user','content':prompt}],tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True).to(model.model.device)
        started=perf_counter()
        with torch.inference_mode():
            output=model.model.generate(**tokens,max_new_tokens=180,do_sample=False,use_cache=True,
                                        repetition_penalty=1.0,no_repeat_ngram_size=0)
        text=model.tokenizer.decode(output[0,tokens['input_ids'].shape[1]:],skip_special_tokens=True)
        try:
            values=json.loads(text)['texts']
            assert len(values)==4 and all(isinstance(v,str) and 4<=len(v)<=240 for v in values)
        except Exception:
            values=[]
        with path.open('a',encoding='utf8') as handle:
            handle.write(json.dumps({'task':i,'scenario':scenario,'expected_contract':key,'texts':values,
                                    'raw_public_output':text,'elapsed_ms':(perf_counter()-started)*1000})+'\n')
        print('INDEPENDENT EVAL GENERATION',i+1,8,len(values),flush=True)


def seal():
    review=json.loads((DATA/'generation_review.json').read_text(encoding='utf8'))
    assert review['reviewed_complete'] and review['reviewer']=='coding agent; not an independent human annotator'
    rows=json.loads((DATA/'sealed_manual.json').read_text(encoding='utf8'))
    raw=list(map(json.loads,(DATA/'independent_qwen_raw.jsonl').read_text(encoding='utf8').splitlines()))
    tasks=independent_generation_tasks()
    accepted=set(review['accepted_keys'])
    for generation in raw:
        task=generation['task'];key,_,kind,ids=tasks[task]
        for j,text in enumerate(generation['texts']):
            if f'{task}:{j}' not in accepted:
                continue
            item=row(text,key,kind,ids,position='FOCUS' if kind=='page' else 'ALL',source='independent offline Qwen')
            item['id']=f'sealed-qwen-{task}-{j}';rows.append(item)
    assert len(rows)>=150
    exact_examples={norm(t) for c in registry() for t in c['examples']}
    assert not any(norm(r['message']) in exact_examples for r in rows), 'Evaluation cannot copy exemplars'
    from collections import Counter
    path=DATA/'sealed.json';write_new(path,rows)
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'path':str(path),'sha256':digest(path),
              'cases':len(rows),'meanings_sha256':meanings_hash(),'registry_sha256':registry_hash(),
              'source_counts':dict(Counter(r['source'] for r in rows)),
              'context_counts':dict(Counter(r['context_kind'] for r in rows)),
              'focus_counts':dict(Counter(str(len(r['context'].get('last_referenced_work_ids',[]))) for r in rows)),
              'under_six_words':sum(len(r['message'].split())<6 for r in rows),
              'order':'Meanings frozen, independent evaluation authored/generated/reviewed, evaluation sealed BEFORE DEV creation.',
              'blindness_limitation':'Same coding agent authored contracts and manual evaluation. Qwen generation was scenario-only, no contract exemplars. Old116/121 are exposed regression, not blind tests.'}
    write_new(ROOT/'reports/assistant_router_v5_sealed_manifest.json',manifest)
    print('V5 EVALUATION SEALED',len(rows),manifest['sha256'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contracts',action='store_true');parser.add_argument('--manual',action='store_true')
    parser.add_argument('--generate',action='store_true');parser.add_argument('--seal',action='store_true');args=parser.parse_args()
    if args.contracts:freeze_contracts()
    if args.manual:manual()
    if args.generate:generate()
    if args.seal:seal()
