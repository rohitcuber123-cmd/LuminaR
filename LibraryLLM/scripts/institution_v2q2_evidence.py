"""Current source inventory and measured Qwen profile export."""
from pathlib import Path
import json,hashlib,re
R=Path(__file__).resolve().parents[1];D=R/'reports'

def main():
 baseline=json.loads((D/'institution_v2q2_checkpoint.json').read_text())
 names=['assistant/qwen.py','assistant/orchestrator.py','assistant/state.py','assistant/tools.py','assistant/library_scope.py',
        'rag/llm.py','rag/qa.py','rag/fast_filter.py','rag/evidence.py','rag/document_grounding.py','rag/citation_boundary.py',
        'rag/services/library_asset_pipeline.py','rag/services/library_asset_routes.py','rag/services/private_documents.py',
        'frontend/src/components/AIChatWidget.tsx','frontend/src/components/assistant/AssistantTurn.tsx','frontend/src/components/ForYou.tsx',
        'frontend/src/pages/LibraryCatalogue.tsx','frontend/src/lib/libraryCatalogue.ts','frontend/src/store/useAssistantStore.ts',
        'frontend/src/hooks/useAssistantPageContext.ts','tests/test_assistant_backend.py','tests/test_document_rag_latency.py',
        'tests/contracts/rag_grounding_v2o2.py','reports/assistant_backend_baseline/hashes.json','reports/document_rag_latency_baseline/manifest.json']
 inventory=[{'path':n,'sha256':hashlib.sha256((R/n).read_bytes()).hexdigest(),'before_sha256':baseline['source_sha256'].get(n),'modified_this_phase':n=='assistant/qwen.py'} for n in names]
 (D/'institution_v2q2_source_versions.json').write_text(json.dumps(inventory,indent=2))
 stages=[json.loads(x) for x in (D/'institution_v2q2_private_stages.jsonl').read_text().splitlines()]
 profiles=[]
 for row in stages:
  final=row.get('final') or {};profile=final.get('profile') or {}
  profiles.append({'library':row['library'],'candidate_in_owned_process_only':row.get('validator_proposal_only_in_owned_process'),'total_request_ms':row['total_ms'],
                   'verdict':final.get('verdict'),'profile':profile,'engine_timing_ms':final.get('timing_ms'),
                   'stages':[{'stage':s['stage'],'elapsed_ms':s['elapsed_ms'],'timing_ms':s.get('timing_ms')} for s in row['stages']]})
 loads=[]
 for name in ['institution_v2q2_lab.log','institution_v2q2_lab_after.log','institution_v2q2_lab_final.log']:
  text=(D/name).read_text(encoding='utf8',errors='replace')
  loads.append({'log':name,'model_load_seconds':[float(x) for x in re.findall(r'Model load\s*:\s*([0-9.]+) seconds',text)]})
 matrix=json.loads((D/'institution_v2q2_candidate_comparison.json').read_text())
 data={'model':'Existing Qwen2.5-3B-Instruct NF4 CUDA0; precision/provider/lock/token caps unchanged','single_model_rule':'Only one resident Qwen process at a time. Local service switched under prior explicit authorization; same resident engine used for all matched validator original/candidate calls. Subsequent serial reloads only verified unprotected prompt revisions.','loads':loads,'private_requests':profiles,'matched_validator_pairs':matrix['matched_pairs'],
       'limitations':['No first-token latency measurement exposed; no value invented.','Direct-matrix tokenizer counts exclude chat framing; end-to-end llm_calls expose actual input/generated tokens.','Request-stage wrappers overlap; do not sum them as disjoint timings.','Private original/candidate runs reuse identical assets but sequential warm-cache differences limit causal latency interpretation. Direct validator pairs alternate order and hold evidence/intent constant.','No production benchmark or broad speed-up claim.','Model-internal rationale unavailable; confidence is not calibration.']}
 traces=[json.loads(x) for x in (D/'institution_v2q2_decision_traces.jsonl').read_text().splitlines()]
 data['assistant_requests']=[{key:row.get(key) for key in ['run_variant','library','execution_mode','request_hash','action','qwen_calls','stages_ms','tools','elapsed_ms','response']} for row in traces]
 (D/'institution_v2q2_latency.json').write_text(json.dumps(data,indent=2))
 print(json.dumps({'source_versions':len(inventory),'private_profiles':len(profiles),'serial_model_loads':len(loads)}))

if __name__=='__main__':main()
