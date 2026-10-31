"""Disclosed reviewed contract migration; never edits historical assertions/gold."""
from pathlib import Path
import json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest

def main():
    tag=sys.argv[1];assert tag.isalnum()
    root='scratch/search_arch9_regression/'
    old=[root+'test_candidate_semantics.py::test_mandatory_missing_value_requests_clarification[titled "A ..."; by Alder Vale]']
    old.extend(root+'test_search_v2c_c4_reviewed_legacy.py::test_curated_candidate_plan['+g+']' for g in ['gold-036','gold-129','gold-130','gold-131','gold-132'])
    review=Path('reports/search_proof6_independent_contract_review.json')
    manifest={'contract':'V7_INHERITS_V6_REVIEWED_COMPATIBILITY_MIGRATION','independent_review':str(review),'independent_review_sha256':hashlib.sha256(review.read_bytes()).hexdigest(),
        'replaced_original_nodes':old,'replacement_source':'scratch/search_architecture_v9/test_reviewed_migration.py','replacement_count':6,
        'original_assertions_or_gold_edited':False,'original_full_run':'reports/search_proof6_attempt4_tests.xml','original_unexplained_failures':0,
        'native_refine_binding':'Frozen legacy assertions bind to candidate refinement.refine; source-only target import change, no expected values changed.'}
    with Path('reports/search_arch9_'+tag+'_migration.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2)
    args=['scratch/search_architecture_v9','scratch/search_arch9_regression','-q','--junitxml=reports/search_arch9_'+tag+'_tests.xml']
    args.extend('--deselect='+n for n in old)
    return pytest.main(args)
if __name__=='__main__':raise SystemExit(main())
