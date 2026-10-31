"""Review package and isolated candidate sources; never edits actual frozen tests."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
STAGE=ROOT/'.scratch/institution-v2o2/proposed'
TEMPLATES=ROOT/'tests/institution_v2o2/candidate_templates'
TRANSPORT=['frontend/src/lib/libraryIntelligence.ts','frontend/src/lib/institutions.ts','frontend/src/lib/api.ts']
BACKEND=['backend/services/library_intelligence_service.py','backend/services/library_intelligence_store.py','backend/routes/library_intelligence.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    baseline=json.loads((R/'institution_v2o2_baseline.json').read_text())
    old=json.loads((R/'institution_v2o1_approval_manifest.json').read_text())
    assert old['J']['sha256']=='23bb4d2d815c78b1fac2ea8323ac4d8a1bb09a829c4e6e6302887b84a1e52a31'
    assert old['RAG']['sha256']=='5ef381d635e60f287c492a256a5ba33cfb916031685da7fefce33515bcdc9d94'
    for k in ('J','RAG'):assert sha(ROOT/old[k]['path'])==old[k]['sha256']
    before=ROOT/'.scratch/institution-v2o2/before/frontend/src/pages/LibraryIntelligence.tsx'
    assert sha(before)==sha(ROOT/'frontend/src/pages/LibraryIntelligence.tsx')==baseline['source_sha256']['frontend/src/pages/LibraryIntelligence.tsx']
    assert sha(before)=='51f58263f2c06fda2bb3f6669de94a735af2d0b97e3cf4497bc154c1375adfd3'
    contract=STAGE/'tests/contracts/staff_boundary_v2o2'
    contract.parent.mkdir(parents=True,exist_ok=True)
    for ext in ('py','cjs'):contract.with_suffix('.'+ext).write_bytes((TEMPLATES/('staff_boundary.'+ext)).read_bytes())
    command=['node',str(contract.with_suffix('.cjs')),str(before),str(ROOT/'frontend/node_modules/typescript')]
    result=json.loads(subprocess.check_output(command,text=True));assert result['ok'],result
    jbaseline=json.loads((R/'institution_v2j_baseline.json').read_text())
    for name in BACKEND:assert sha(ROOT/name)==jbaseline['source_sha256'][name]
    manifest={'schema':1,'reviewed_page_origin_sha256':sha(before),
              'page_executable_sections':result['sections'],
              'full_transport_modules':{name:sha(ROOT/name) for name in TRANSPORT},
              'backend_authority':{name:jbaseline['source_sha256'][name] for name in BACKEND},
              'boundary':'All executable AST retained. Passive JSX text/wrappers and fixed literal presentation attributes may evolve. No arbitrary JS expressions or imported capabilities are ignored.'}
    contract.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    rag_name='tests/contracts/rag_grounding_v2o2.py'
    (STAGE/rag_name).write_bytes((ROOT/'.scratch/institution-v2o1/proposed/tests/contracts/rag_grounding_v2o1.py').read_bytes())
    names=['tests/contracts/staff_boundary_v2o2.'+x for x in ('py','cjs','json')]+[rag_name]
    fingerprints={n:hashlib.sha256((STAGE/n).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for n in names}
    jpath='tests/institution_v2j/test_diagnostics.py';original=(ROOT/jpath).read_bytes().decode()
    proposal=original.replace("'backend/routes/library_intelligence.py','frontend/src/pages/LibraryIntelligence.tsx']:","'backend/routes/library_intelligence.py']:")
    insertion='    # Proposed O.2: full transport and executable authority boundary, UX remains evolvable.\n'
    for n in names[:3]:insertion+=f"    assert hashlib.sha256((ROOT/{n!r}).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=={fingerprints[n]!r}\n"
    insertion+='    from tests.contracts.staff_boundary_v2o2 import assert_staff_contract\n    assert_staff_contract(ROOT)\n'
    proposal=proposal.replace('    # Part2L explicitly integrates the native worker.',insertion+'    # Part2L explicitly integrates the native worker.')
    assert proposal!=original
    rpath='tests/test_assistant_backend.py';roriginal=(ROOT/rpath).read_bytes().decode()
    old_assert="            assert hashlib.sha256(Path(row['Path']).read_bytes()).hexdigest().upper() == row['Hash']"
    new_assert="            relative = Path(row['Path']).relative_to(Path(rows[0]['Path']).parents[1])\n            payload = (ROOT / relative).read_bytes()\n            if relative.as_posix() == 'rag/qa.py':\n"
    new_assert+=f"                assert hashlib.sha256((ROOT/{rag_name!r}).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=={fingerprints[rag_name]!r}\n"
    new_assert+="                from tests.contracts.rag_grounding_v2o2 import reviewed_rag_payload\n                payload = reviewed_rag_payload(payload)\n            assert hashlib.sha256(payload).hexdigest().upper() == row['Hash']"
    rproposal=roriginal.replace(old_assert,new_assert)
    manifest_path='reports/assistant_backend_baseline/hashes.json'
    manifest_line="    rows = json.loads((ROOT / 'reports/assistant_backend_baseline/hashes.json').read_text(encoding='utf-8-sig'))"
    rproposal=rproposal.replace(manifest_line,f"    assert hashlib.sha256((ROOT/{manifest_path!r}).read_bytes()).hexdigest()=={sha(ROOT/manifest_path)!r}\n"+manifest_line)
    assert rproposal!=roriginal

    def patch(label,edits):
        text=''
        for name,before,after in edits:
            text+=f'diff --git a/LibraryLLM/{name} b/LibraryLLM/{name}\n'
            if not before:text+='new file mode 100644\n'
            text+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/LibraryLLM/'+name if before else '/dev/null',tofile='b/LibraryLLM/'+name))
        target=R/f'institution_v2o2_{label}_approval.patch';target.write_bytes(text.replace('\r\n','\n').encode('utf8'))
        run=subprocess.run(['git','apply','--check','--ignore-space-change',str(target)],cwd=ROOT.parent,capture_output=True,text=True)
        assert run.returncode==0,run.stderr
        return {'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),'apply_check':True,'applied_to_actual_tree':False}
    j=patch('j',[(jpath,original,proposal),*[(n,'',(STAGE/n).read_bytes().decode()) for n in names[:3]]])
    rag=patch('rag',[(rpath,roriginal,rproposal),(rag_name,'',(STAGE/rag_name).read_bytes().decode())])
    # Stage test files separately for actual pytest execution, not AST-only tests.
    for n,t in ((jpath,proposal),(rpath,rproposal)):
        p=STAGE/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.encode())
    result={'status':'AWAITING_SEPARATE_USER_APPROVAL','J':j,'RAG':rag,'helper_fingerprints':fingerprints,
            'full_transport_modules':manifest['full_transport_modules'],'original_proposals_unchanged':True,
            'actual_protected_tests_or_implementation_modified':False,
            'rag_additional_assertions':'Pin original manifest bytes; resolve its immutable legacy absolute paths relative to the tested checkout so candidate mutations are actually tested.'}
    (R/'institution_v2o2_approval_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'patches':2,'actual_tree_applied':False,'source_boundary_sections':len(result['helper_fingerprints'])}))


if __name__=='__main__':main()
