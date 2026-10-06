"""DEV-only bounded positions: definitions, structural defaults, tiny scorer."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
from assistant.router_v5.matcher import Matcher
from assistant.router_v5.binding import make_plan,model_payload
from assistant.router_v5.contracts import BY_ID
from assistant.semantic import bind_position
from router_v5_evidence import write

def main():
    if (ROOT/'reports/assistant_router_v5_candidate_seal.json').exists():raise SystemExit('Candidate frozen')
    import numpy as np,torch
    matcher=Matcher(False)
    rows=json.loads((ROOT/'evaluation/assistant_router_v5/dev.json').read_text(encoding='utf8'))
    rows=[r for r in rows if BY_ID[r['contract_id']].context in {'book','book_access'}]
    with torch.inference_mode():
        vectors=matcher.encoder.encode([model_payload(r['message'],make_plan(r['context'],r['message']))['message'] for r in rows],normalize_embeddings=True,show_progress_bar=False)
    sims=vectors@matcher.vectors.T
    results=[]
    for i,r in enumerate(rows):
        plan=make_plan(r['context'],r['message']);bank=matcher.aux_indices['position'];predictions={}
        definitions={label:float(sims[i,idx[0]]) for label,idx in bank.items()}
        scorer={label:float(.85*sims[i,idx[1:]].max()+.15*sims[i,idx[0]]) for label,idx in bank.items()}
        predictions['A_definitions']=max(definitions,key=definitions.get)
        predictions['B_structural']='FOCUS' if len(plan.ids)==1 or len(plan.focus)==1 else 'ALL'
        predictions['C_tiny_semantic_scorer']=max(scorer,key=scorer.get)
        checks={}
        for method,position in predictions.items():
            try:checks[method]=bind_position(list(plan.ids),position,list(plan.focus))==r['expected_ids']
            except ValueError:checks[method]=False
        results.append({'id':r['id'],'expected_position':r['position'],'predictions':predictions,'bound_ids_correct':checks})
    write('position_comparison',{'source':'DEV only, no training; same curated static banks as frozen registry.',
          'cases':results,'metrics':{method:{'correct':sum(r['bound_ids_correct'][method] for r in results),'total':len(results)} for method in predictions},
          'decision':'Calibrated tiny exemplar/definition scorer with structural binding; uncertainty falls back. Structural defaults alone cannot resolve ordinals/OTHER.',
          'cuda_initialized':torch.cuda.is_initialized(),'rss_mb':matcher.audit['rss_mb']})

if __name__=='__main__':main()
