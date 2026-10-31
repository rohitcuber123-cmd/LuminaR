"""Project only shuffled queries and authoritative native contract to separate reviewer."""
from pathlib import Path
import json,hashlib,random

R=Path('reports');P='search_combined8_'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(n,d):
    with (R/(P+n+'.json')).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False)


def main():
    authored=[json.loads(s) for s in (R/(P+'authored.jsonl')).read_text(encoding='utf-8').splitlines()]
    random.Random(80629).shuffle(authored);mapping={};queries=[]
    for i,g in enumerate(authored,1):
        rid=f'R8-{i:04d}';mapping[rid]=g['case_id']
        queries.append(dict(review_id=rid,**{k:g[k] for k in ['query_text','scope_type','workspace_type','search_mode']}))
    brief=json.loads((R/(P+'author_brief.json')).read_text(encoding='utf-8'))
    schema=dict(brief['schema']);schema['scalar_fields']=schema['scalar_fields']+['physical_available_only','include_terms']
    contract=dict(brief['source_only_contract']);contract.pop('original_pilot_applicability',None)
    packet=dict(task='Independently label ALL supplied queries from source and authoritative capabilities. Author labels/family/strata are withheld. Candidate code/tests/predictions/outcomes and target accuracy are forbidden.',
                queries=queries,scopes=brief['scopes'],schema=schema,normative_rules=brief['normative_rules'],
                source_only_contract=contract,corrections_to_older_native_description=brief['corrections_to_older_native_description'],
                native_representation_addendum=[
                    'Every executable row needs explicit full scalar present/absent masks for every listed scalar, plus sort. Absence: list=[],scalar=None,bool=False. APPLICABLE_ABSENCE must be used for known absence, not N/A.',
                    'physical_available_only bool is false absent. Physical requestability requirement makes it true along with formats PHYSICAL and the source-backed availability value.',
                    'include_terms duplicates the canonical subjects list. Declare the same list if mandatory subjects exist; [] when absent.',
                    'AVAILABLE_NOW accepts circulating with requestable_count>0 OR online access; REQUESTABLE accepts circulating with requestable_count>0 only. physical_available_only additionally requires physical requestability. Exact language compares native book.language case/whitespace-normalized.',
                    'Global native capabilities do not support year/language/availability; supplied source operands can remain diagnostic while execution is unsupported. No support invented from recognizing a domain.',
                    'PARTIALLY_APPLICABLE is only a common supplied subset of a list, with resolved_value. UNRESOLVED and N/A exclusions require reasons. Do not turn an absent known field into an unscored field.',
                    'Keep exact notice subtype unscored only under source-defined OPTIONAL mask with acceptable_decisions=[EXECUTABLE,EXECUTABLE_WITH_NOTICE]. Actual source repair requires REQUIRED EWN.',
                    'If source semantics are genuinely irresolvable under the frozen contract, exclude_from_acceptance=true with exclusion_reason; do not force an oracle. Preserve supplied query exactly.',
                    'Source role annotations use exact unique substrings where objectively defensible. Do not claim arbitrary semantic equivalence or live visibility/JWT behavior.'],
                outputs=['reports/search_combined8_independent_review.jsonl','reports/search_combined8_reviewer_provenance.json'],
                output_row_keys=['review_id','expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','expected_sort','expected_semantic_remainder','expected_soft_preferences','expected_source_roles','semantic_justification','notice_policy','acceptable_decisions','expected_unadapted_mandatory_assertions','expected_notices'],
                allowed_reads_only=['reports/search_combined8_blind_reviewer_packet.json'],
                forbidden=['candidate code/tests','any predictions/results','author gold or historical gold/query corpora','sealed data','network/Mongo/model inference APIs','desired scores'],
                provenance='Separate AI normative reviewer, human0; candidate remains frozen and no primary capture has occurred')
    save('reviewer_id_map',mapping);save('blind_reviewer_packet',packet)
    print(json.dumps(dict(queries=len(queries),packet_sha256=sha(R/(P+'blind_reviewer_packet.json')),author_labels_exposed=False)))

if __name__=='__main__':main()
