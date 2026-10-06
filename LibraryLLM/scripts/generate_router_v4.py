"""Offline local-Qwen paraphrases; semantic labels always come from seeds."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from router_v4_data import seed_rows,norm

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seed',type=int,default=947);args=parser.parse_args()
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    from pydantic import BaseModel,Field
    from rag.llm import LuminaRLLM
    class Paraphrases(BaseModel):
        texts:list[str]=Field(min_length=4,max_length=4)
    path=ROOT/'training/assistant_router_v4';path.mkdir(exist_ok=True,parents=True)
    checkpoint=path/'generation_raw.jsonl';done={}
    if checkpoint.exists():done={r['seed_id']:r for r in map(json.loads,checkpoint.read_text(encoding='utf8').splitlines())}
    seeds=seed_rows();(path/'seeds.json').write_text(json.dumps(seeds,indent=2),encoding='utf8')
    torch.manual_seed(args.seed);llm=LuminaRLLM()
    for i,s in enumerate(seeds):
        if s['seed_id'] in done and done[s['seed_id']]['valid_format']:continue
        if int(s['seed_id'].split(':')[-1]) not in {0,1,2,4}:
            with checkpoint.open('a',encoding='utf8') as f:
                f.write(json.dumps({'seed_id':s['seed_id'],'texts':[], 'valid_format':True,'manual_only':True})+'\n')
            continue
        styles=['a casual short question','an indirect statement of the same request','a formal detailed request','an elliptical conversational request']
        prompt='Rewrite this library request in four distinct styles, at most 14 words each. Keep EXACT meaning, action, timeframe, plurality and negation. Do not answer. No added preference, named book, emoji, emoticon or filler. Every {placeholder} MUST appear exactly once, unchanged. Return ONLY JSON {"texts":[four strings]}, no markdown. Styles: '+', '.join(styles)+'. Request: '+s['message']
        messages=[{'role':'system','content':'You are an offline paraphrase writer. Preserve placeholders and meaning precisely.'},{'role':'user','content':prompt}]
        tokens=llm.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True).to(llm.model.device)
        started=perf_counter()
        with torch.inference_mode():
            result=llm.model.generate(**tokens,max_new_tokens=180,do_sample=False,use_cache=True,
                repetition_penalty=1.0,no_repeat_ngram_size=0)
        text=llm.tokenizer.decode(result[0,tokens['input_ids'].shape[1]:],skip_special_tokens=True)
        try:values=Paraphrases.model_validate_json(text).texts
        except Exception:values=[]
        record={'seed_id':s['seed_id'],'texts':values,'raw_public_generation':text,'duration_ms':(perf_counter()-started)*1000,'valid_format':bool(values)}
        with checkpoint.open('a',encoding='utf8') as f:f.write(json.dumps(record)+'\n')
        print('GENERATED',i+1,len(seeds),s['seed_id'],len(values),flush=True)
    print('GENERATION COMPLETE',flush=True)

if __name__=='__main__':main()
