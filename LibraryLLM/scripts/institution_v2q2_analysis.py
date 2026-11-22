"""Summarize every original/candidate run; no outcome filtering."""
from pathlib import Path
from statistics import median
import json,hashlib
R=Path(__file__).resolve().parents[1];D=R/'reports'

def main():
 matrix=json.loads((D/'institution_v2q2_validator_matrix.json').read_text());assert matrix['complete']
 groups={}
 for variant in ['original','candidate']:
  rows=[x for x in matrix['cases'] if x['variant']==variant]
  negatives=[x for x in rows if x['expected_verdict']=='NOT_SUPPORTED'];positive=[x for x in rows if x['expected_verdict']=='SUPPORTED']
  groups[variant]={'runs':len(rows),'matched_expectation':sum(x.get('pass',False) for x in rows),'positive_acceptance':[sum(x.get('actual_verdict')=='SUPPORTED' for x in positive),len(positive)],'strict_negative_acceptance':[sum(x.get('actual_verdict')=='SUPPORTED' for x in negatives),len(negatives)],'correct_abstention':[sum(x.get('actual_verdict')=='NOT_SUPPORTED' for x in negatives),len(negatives)],'qwen_calls':sum(len(x['qwen_calls']) for x in rows),'median_validator_ms':median(x['elapsed_ms'] for x in rows),'failed_cases':[{'id':x['id'],'repeat':x.get('repeat',1),'expected':x['expected_verdict'],'actual':x.get('actual_verdict')} for x in rows if not x.get('pass')]}
 paired=[]
 for orig in [x for x in matrix['cases'] if x['variant']=='original']:
  cand=next(x for x in matrix['cases'] if x['variant']=='candidate' and x['id']==orig['id'] and x.get('repeat',1)==orig.get('repeat',1))
  assert orig['question']==cand['question'] and orig['texts']==cand['texts'] and orig['structured_intent']==cand['structured_intent']
  paired.append({'case':orig['id'],'repeat':orig.get('repeat',1),'original_ms':orig['elapsed_ms'],'candidate_ms':cand['elapsed_ms'],'candidate_minus_original_ms':cand['elapsed_ms']-orig['elapsed_ms']})
 ab={}
 for variant,filename in [('original','institution_v2q2_private_qwen.json'),('candidate','institution_v2q2_private_candidate.json')]:
  rows=json.loads((D/filename).read_text());assert len(rows)==12
  ab[variant]={label:{'owner_runs':sum(x['user']=='owner' and x['library']==label for x in rows),'correct_fact_answers':sum(x['user']=='owner' and x['library']==label and x['expected_synthetic_fact_present'] for x in rows),'outsider_denials':sum(x['user']=='outsider' and x['library']==label and x['http']==404 for x in rows),'owner_median_ms':median(x['elapsed_ms'] for x in rows if x['user']=='owner' and x['library']==label)} for label in ['A','B']}
 data={'matrix':groups,'matched_pairs':paired,'private_AB':ab,'decision':'DO_NOT_APPLY_CANDIDATE: expanded tests expose unsupported entity/field/value acceptances. Existing validator also has limitations. Protected approval absent.',
       'test_oracle':'Authored strict claim-grounding expectations. Yes/no and contradictory-record questions can admit a corrective answer under other answerability policies; rows retain exact questions/evidence. Wrong entity/field/absent-value failures are decisive independent of that ambiguity.',
       'scope_limits':['29 matched pairs:25categories plus4bounded repeats, not a calibrated safety rate.','Categories19/20 are deliberately raw-validator provenance challenges, not authorization bypasses; actual HTTP denial tested independently.','No matrix final answers generated. Full A/B answers are synthetic and retained.','Same model, method schema, temperature, token cap, source/evidence and authored intent per pair; order alternates. No retrieval or source change between matched original/candidate experiments.','Candidate experiment completed before separate unprotected reference-example repair.','Confidence is model self-report; no calibration or semantic accuracy inferred.','No first-token latency available. Plain tokenizer encode counts in direct matrix exclude chat framing; exact runtime counts are exposed in end-to-end profiles.']}
 (D/'institution_v2q2_candidate_comparison.json').write_text(json.dumps(data,indent=2))
 stages=[json.loads(x) for x in (D/'institution_v2q2_private_stages.jsonl').read_text().splitlines()]
 (D/'institution_v2q2_private_B_analysis.json').write_text(json.dumps({'root_cause':'Evidence-stage false negative: expected B fact retained in prepared chunks/retrieval/reranking/context/validator input, then original NOT_SUPPORTED. Judge internal rationale not exposed.','AB':ab,'stages':stages,'protected_implementation_fixed':False,'candidate_recommended':False},indent=2))
 lines=['# Exact validator comparison','',data['decision'],'', '|Case|Repeat|Question|Expected|Original|Candidate|','|---|---:|---|---|---|---|']
 for orig in [x for x in matrix['cases'] if x['variant']=='original']:
  cand=next(x for x in matrix['cases'] if x['variant']=='candidate' and x['id']==orig['id'] and x.get('repeat',1)==orig.get('repeat',1))
  lines.append('|'+ '|'.join(map(str,[orig['id'],orig.get('repeat',1),orig['question'],orig['expected_verdict'],orig.get('actual_verdict'),cand.get('actual_verdict')]))+'|')
 lines.extend(['',data['test_oracle'],'','Evidence, entity/field oracles, provenance, structured intent, raw model JSON and timings for all58runs: institution_v2q2_validator_matrix.json. No failed run discarded.'])
 (D/'institution_v2q2_validator_matrix.md').write_text('\n'.join(lines),encoding='utf8')
 original=D/'institution_v2q1d_protected_validator_proposal.patch';copy=D/'institution_v2q2_protected_validator_proposal.patch';copy.write_bytes(original.read_bytes())
 (D/'institution_v2q2_approval_record.json').write_text(json.dumps({'approved':False,'source_applied':False,'guard_applied':False,'patch_sha256':hashlib.sha256(copy.read_bytes()).hexdigest(),'recommendation':data['decision'],'qa_unchanged':True,'required_contract_changes':'See institution_v2q2_validator_review.md; no arbitrary-version exception or manifest rebaseline allowed.'},indent=2))
 print(json.dumps({'matrix':groups,'AB':ab},indent=2))

if __name__=='__main__':main()
