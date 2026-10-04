"""Offline tokenizer-only prompt audit reconstructed from frozen source IDs."""
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from transformers import AutoTokenizer
from rag.qa import LuminaRAG
from rag.llm import MODEL_NAME,SYSTEM_MESSAGE
from rag.document_latency import compact_answer

def main():
    tokenizer=AutoTokenizer.from_pretrained(MODEL_NAME,local_files_only=True)
    rows=json.loads((ROOT/'reports/document_rag_baseline_raw.json').read_text())['runs']
    chunks={}
    for path in (ROOT/'rag/chunks').glob('*.json'):
        value=json.loads(path.read_text(encoding='utf-8'))
        for c in value if isinstance(value,list) else value.get('chunks',[]):chunks[c['chunk_id']]=c
    fake=SimpleNamespace(compact_prompt=True,build_compact_prompt=lambda q,c,d:LuminaRAG.build_compact_prompt(None,q,c,d))
    def tokens(s):return len(tokenizer.encode(s,add_special_tokens=False))
    def formatted(p):return tokenizer.apply_chat_template([{'role':'system','content':SYSTEM_MESSAGE},{'role':'user','content':p}],tokenize=False,add_generation_prompt=True)
    result={'model_loaded':False,'tokenizer_only':True,'rows':[]}
    for row in rows:
        if row['round']!=1 or row['case'] not in {'rbac_definition','roles','indexing'}:continue
        sources=row['rag']['sources'];parts=[];headers=[];texts=[]
        for n,source in enumerate(sources,1):
            c=chunks[source['chunk_id']];header=f'[Source {n}]\n'
            for label,key in [('Book','title'),('Author','author'),('Chapter','chapter')]:
                if source.get(key):header+=f'{label}: {source[key]}\n'
            if c.get('page') is not None:header+=f'Page: {c["page"]}\n'
            header+=f'File: {c["filename"]}\n\n'
            text=c['text'].strip();headers.append(header);texts.append(text);parts.append(header+text+'\n')
        context='\n'.join(parts);old=LuminaRAG.build_prompt(fake,row['question'],context,'normal');new=compact_answer(row['question'],context,'normal')
        assert hashlib.sha256(old.encode()).hexdigest()==next(p['prompt_sha256'] for p in row['observation']['prompts'] if p['purpose']=='answer')
        item={'case':row['case'],'system_tokens':tokens(SYSTEM_MESSAGE),'question_tokens':tokens(row['question']),
              'evidence_body_tokens':sum(map(tokens,texts)),'source_header_tokens':sum(map(tokens,headers)),
              'context_tokens':tokens(context),'duplicate_question_count':old.count(row['question']),
              'duplicate_passage_bodies':len(texts)-len(set(texts)),
              'repeated_filename_headers':len(headers)-len({s['filename'] for s in sources}),
              'old_instruction_and_format_tokens':tokens(old.replace(context,'').replace(row['question'],'')),
              'new_instruction_and_format_tokens':tokens(new.replace(context,'').replace(row['question'],'')),
              'baseline_formatted_tokens':tokens(formatted(old)),'optimized_formatted_tokens':tokens(formatted(new)),
              'context_byte_identical':context in old and context in new}
        samples=[]
        for _ in range(20):
            started=time.perf_counter();tokenizer.encode(formatted(old),add_special_tokens=False);samples.append((time.perf_counter()-started)*1000)
        item['warm_full_tokenization_median_ms']=__import__('statistics').median(samples)
        result['rows'].append(item)
    result['static_prefix_cache_decision']='No new cache: full warm tokenization is milliseconds versus multi-second generation; shared system prefix is only 60 tokens. Existing trie/token-enforcer cache retained.'
    (ROOT/'reports/document_rag_prompt_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
