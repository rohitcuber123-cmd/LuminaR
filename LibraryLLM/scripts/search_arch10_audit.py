"""Evidence-backed registry, license and hardware audit; never loads weights."""
from pathlib import Path
import json,hashlib,ast,urllib.request,subprocess,platform,sys
from datetime import datetime,timezone
import psutil

R=Path('reports')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
    with (R/name).open('x',encoding='utf8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)


def main():
    review=json.loads((R/'search_arch10_source_contract_review.json').read_text(encoding='utf8'))
    evidence={p:sha(p) for p in review['source_files']}
    scoped={}
    for s in ['GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF']:
        local=s!='GLOBAL'
        scoped[s]=dict(rating=True,year=local,language=local,availability=local,
            formats=['ONLINE','PHYSICAL','BOTH'] if local else ['ONLINE'],sort=True,semantic_retrieval='INTERFACE_PRESENT_RUNTIME_UNVERIFIED',
            authorization='BACKEND_BEFORE_FACETS_AND_AGAIN_BEFORE_HYDRATION',
            online_meaning='TENANT_HYDRATED_ONLINE_CAPABILITY' if local else 'ACTOR_ACTIVE_BORROW_READABLE_ENTITLEMENT')
    common=dict(source='immutable original query; [start,end) Unicode spans; bounded repair provenance',
        hard_filter='Only supported mandatory resolved source-owned operands',
        retrieval='Candidate generation is bounded; current hydrated record checked with native matches before pagination',
        pagination='Filter and sort before slicing within bounded candidate universe; not whole-catalog recall/completeness',
        missing_data='Required positive operands fail native predicate if data unavailable; negative format accepts absence (not proof of known absence)',
        errors='Candidate adapter fails closed; production tenant encoder failure has lexical fallback, not guaranteed equivalent semantic relevance')
    fields={
      'title':dict(native=['title_text'],operand='string',operators=['NORMALIZED_SUBSTRING_TITLE_OR_AUTHOR'],
          semantics='Title OR joined author normalized substring. General/approximate discovery allowed; fuzzy candidate selection followed by matches.',
          negation=False,strict_title_only=False,normalized_equality=False,exact_quoted_literal=False),
      'literal':dict(native=['exact_text'],operand='string',operators=['NORMALIZED_TITLE_OR_IDENTIFIER_EQUALITY'],
          semantics='Normalized title equality OR supported identifier; not byte/punctuation equality or exclusive title-domain equality.',negation=False),
      'author':dict(native=['author_text'],operand='string',operators=['NORMALIZED_SUBSTRING'],negation=False),
      'subject':dict(native=['subjects','include_terms','exclude_subjects'],operand='scope-canonical subject string',operators=['ALL','NOT_ANY'],negation=True),
      'exclude':dict(native=['exclude_terms'],operand='string',operators=['WHOLE_WORD_TEXT_NOT'],negation=True,
          semantics='Normalized searchable title/authors/subjects/description text; word boundaries, not publisher/author exclusion alias.'),
      'rating':dict(native=['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive'],operand='finite number 0..5',
          operators=['>','>=','<','<=','=','RANGE'],negation='Only represented numeric complement single interval; disjoint intervals unsupported',missing_data='Missing/NaN/rating zero without count excluded for positive bounds'),
      'year':dict(native=['year_min','year_max','year_min_exclusive','year_max_exclusive'],operand='integer 1000..2100',operators=['>','>=','<','<=','=','RANGE'],
          negation='Only represented single interval',semantics='publication_year, else parseable first_publish_date; global disabled by scope'),
      'language':dict(native=['language'],operand='string',operators=['NORMALIZED_EQUALITY'],negation=False),
      'format':dict(native=['formats','excluded_formats','exclusive_formats'],operand='ONLINE/PHYSICAL/BOTH',operators=['PRESENT','NOT','ONLY'],negation=True,
          semantics='True capability flags; ONLY requires opposite-format exclusion in native projection. Missing negative flag is accepted by native matches.',
          production_defect='Global negative-only ONLINE fails to load entitlement set; candidate adapter hydrates it for every global query. No production repair applied.'),
      'availability':dict(native=['availability','physical_available_only'],operand='AVAILABLE_NOW/REQUESTABLE/PHYSICAL_NOW/PHYSICAL_REQUESTABLE',operators=['PRESENT'],negation=False,
          semantics='REQUESTABLE needs CIRCULATING and requestable_count>0. AVAILABLE_NOW also admits online. Physical-only flag requires requestability.'),
      'sort':dict(native=['sort'],operand='enum',operators=['TITLE_ASC','RATING_DESC','NEWEST_DESC','RELEVANCE_PROVIDER'],negation=False,
          semantics='NEWEST sorts publication_year only; differs from filtering fallback first_publish_date. Missing sort data uses native zero/empty fallback.'),
      'semantic':dict(native=['semantic_text'],operand='free-form string',operators=['PROVIDER_DISCOVERY'],negation=False,
          semantics='No mandatory metadata may be silently removed into text. Advice passed as semantic provider text by isolated adapter; actual relevance unverified.'),
      'page_count':dict(native=[],operand='number',operators=[],negation=False,hard_filter=False),
      'price':dict(native=[],operand='commercial price comparison',operators=[],negation=False,hard_filter=False,
          semantics='Free-to-borrow is semantic access preference; no commercial price operand implied.'),
      'publisher':dict(native=[],operand='string',operators=[],negation=False,hard_filter=False),
      'edition':dict(native=[],operand='string',operators=[],negation=False,hard_filter=False),
    }
    for f,v in fields.items():
        v['scopes']={s:(False if f in ['page_count','price','publisher','edition'] else scoped[s].get(f,True)) for s in scoped}
        v.setdefault('hard_filter',f!='semantic');v['enforcement_contract']=common
    write('search_arch10_capability_registry.json',dict(version='V10-capability-registry-v2',
        status='SOURCE_AUDITED_COMPONENT_CONTRACT_NOT_RUNTIME_QUALIFICATION',scopes=scoped,fields=fields,source_hashes=evidence,
        independent_review='reports/search_arch10_source_contract_review.json',
        changes_from_v9=['Removed false title normalized equality and author negation promises','Specified exact normalized title-or-identifier lookup',
          'Scoped global online to readable borrowing entitlements','Recorded negative-only global native defect and isolated repair',
          'Fixed sort directions and availability semantics','Separated hard-filter soundness from candidate completeness'],
        source_only_migration=dict(title_only_substring='MIGRATED_WITH_REPLACEMENT_TESTS',missing_pages='IMPLEMENTATION_REPAIRED_TO_INCOMPLETE_NO_MIGRATION')))
    cache=Path.home()/'.cache/huggingface/hub/models--Qwen--Qwen2.5-3B-Instruct'
    revision=(cache/'refs/main').read_text().strip()
    snapshot=cache/'snapshots'/revision
    license_url=f'https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/raw/{revision}/LICENSE'
    local_license=snapshot/'LICENSE'
    # License metadata only. Do not download model files or mutate HF cache.
    content=local_license.read_bytes() if local_license.exists() else urllib.request.urlopen(license_url,timeout=20).read()
    assert content.startswith(b'Qwen RESEARCH LICENSE AGREEMENT')
    lic=R/'search_arch10_pinned_Qwen_LICENSE.txt'
    with lic.open('xb') as f:f.write(content)
    config=snapshot/'config.json'
    memory=dict(psutil.virtual_memory()._asdict())
    try:gpu=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10).stdout.strip()
    except (OSError,subprocess.TimeoutExpired):gpu='UNAVAILABLE'
    write('search_arch10_resource_license_audit.json',dict(measured_at_utc=datetime.now(timezone.utc).isoformat(),
        hardware=dict(platform=platform.platform(),python=sys.executable,logical_cpus=psutil.cpu_count(),ram=memory,gpu=gpu),
        model=dict(repository='Qwen/Qwen2.5-3B-Instruct',revision=revision,local_license_present=local_license.exists(),
          license_source=license_url,license_artifact=str(lic).replace('\\','/'),license_sha256=sha(lic),license='Qwen Research License',
          historical_v9_apache_statement='INCORRECT_SUPERSEDED_BY_THIS_AUDIT_HISTORY_UNEDITED',
          permitted_scope='Research/evaluation subject to license conditions; commercial use requires separate licensor permission',
          commercial_clearance='NOT_ESTABLISHED',config_sha256=sha(config),weight_downloads=0,new_predictions=0,training_runs=0),
        extractor=dict(required=False,evaluated='COMPACT_INTERFACE_INHERITED_TESTS_ONLY_NO_NEW_MODEL_PREDICTIONS',
          rationale='No demonstrated learned benefit; historical 0/2 source-valid predictions and tens-of-seconds latency do not justify a hot-path dependency.',
          memory_policy='Model-specific estimated peak plus platform reserve; never require 16GB free on a 16GB host.'),
        runtime_health='UNVERIFIED_NO_SERVICE_OR_LIVE_INDEX_PROBE',real_relevance='UNVERIFIED_NO_INDEPENDENT_BOOK_RELEVANCE_ORACLE'))
    print('registry/source/license/resource audit written')

if __name__=='__main__':main()
