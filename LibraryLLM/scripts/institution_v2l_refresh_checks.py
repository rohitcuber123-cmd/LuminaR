"""Refresh only the two affected groups after the explicit historical guard adaptation."""
import hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
path=R/'institution_v2l_final_backend.json'
rows=json.loads(path.read_text(encoding='utf8'))
assert rows[-1]['group']=='events','Full frozen run must finish first'
for name in ['institution_v2j','institution_v2l']:
    tree=ET.parse(R/f'institution_v2l_final_{name}.xml');cases=list(tree.iter('testcase'))
    failed=sum(any(c.tag in ['failure','error'] for c in t) for t in cases)
    skipped=sum(any(c.tag=='skipped' for c in t) for t in cases)
    assert not failed,(name,failed)
    old=next(g for g in rows if g['group']==name)
    old.update(tests=len(cases),passed=len(cases)-failed-skipped,failed=failed,skipped=skipped,exit=0,
        seconds=sum(float(s.attrib.get('time','0')) for s in tree.iter('testsuite')),
        rerun_reason='Explicit native-integration guard adaptation plus original-SHA-pinned protocol test; all unaffected groups retained from the full final run.')
path.write_text(json.dumps(rows,indent=2),encoding='utf8')
baseline=json.loads((R/'institution_v2j_baseline.json').read_text(encoding='utf8'))
golden=ROOT/'tests/institution_v2l/fixtures/native_worker_before.txt'
data={'initial_new_failure':'tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged',
    'initial_evidence':['institution_v2l_initial_guard_institution_v2j.xml','institution_v2l_initial_guard_institution_v2j.log'],
    'reason':'Historical J test pinned the entire native worker file; L explicitly authorizes a per-instance native observer seam.',
    'adaptation':'J test retains exact Staff service/store/route/frontend hashes. Native worker is now checked by a new L test that pins the original J source SHA, compares the whole run_one protocol after removing only two observer statements/three progress-forwarding calls, checks unchanged semantic implementation/store hash, and is supplemented by lifecycle/mutation/fencing tests.',
    'baseline_hashes_rebased':False,'protected_RAG_and_lexical_tests_changed':False,'tests_skipped_suppressed_or_xfailed':False,
    'original_native_sha256':baseline['source_sha256']['search/library_intelligence.py'],'golden_sha256':hashlib.sha256(golden.read_bytes()).hexdigest(),
    'final_J':next(g for g in rows if g['group']=='institution_v2j'),'final_L':next(g for g in rows if g['group']=='institution_v2l')}
assert data['original_native_sha256']==data['golden_sha256']
(R/'institution_v2l_guard_review.json').write_text(json.dumps(data,indent=2),encoding='utf8')
print(json.dumps({k:sum(g.get(k,0) for g in rows) for k in ['tests','passed','failed','skipped']}))
