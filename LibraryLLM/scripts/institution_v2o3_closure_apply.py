"""Apply only the two exact user-approved patches, with strict preimages."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
EXPECTED={'J':('institution_v2o3_j_approval.patch','bfd376271d10b5e285c89ebce96b5470b2b8f95ff4a61c38cd9c0d306687bf2a'),
          'RAG':('institution_v2o3_rag_approval.patch','76c09bfef7e676595e0af6974e55aa232e63c684ec51961c558eabf97e45431b')}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    record=R/'institution_v2o3_closure_application.json'
    assert not record.exists(),'Refusing to repeat approved patch application'
    prior=json.loads((R/'institution_v2o3_baseline.json').read_text())
    manifest=json.loads((R/'institution_v2o3_approval_manifest.json').read_text())
    for key,(name,digest) in EXPECTED.items():assert sha(R/name)==digest==manifest[key]['sha256'],f'APPROVED_PATCH_DIGEST_MISMATCH:{key}'
    for name in ['tests/institution_v2j/test_diagnostics.py','tests/test_assistant_backend.py','rag/qa.py',*manifest['full_transport_modules'],*manifest['backend_authority']]:
        assert sha(ROOT/name)==prior['source_sha256'][name],f'REVIEWED_PREIMAGE_CHANGED:{name}'
    assert (ROOT/'reports/assistant_backend_baseline/hashes.json').read_bytes()==(ROOT/'.scratch/institution-v2o3/before/reports/assistant_backend_baseline/hashes.json').read_bytes()
    additions=['tests/contracts/staff_boundary_v2o3.py','tests/contracts/staff_boundary_v2o3.cjs','tests/contracts/staff_boundary_v2o3.json','tests/contracts/rag_grounding_v2o2.py']
    for name in additions:assert not (ROOT/name).exists(),f'APPROVED_NEW_FILE_ALREADY_EXISTS:{name}'
    paths=[str(R/name) for name,_ in EXPECTED.values()]
    # Same reviewed application method as the preparation checks. Strict byte
    # preimage checks above ensure the whitespace option handles CRLF context
    # only; it is not used to accept a drifted protected test or product source.
    command=['git','apply','--ignore-space-change',*paths]
    check=subprocess.run(['git','apply','--check','--ignore-space-change',*paths],cwd=ROOT.parent,capture_output=True,text=True)
    if check.returncode:raise RuntimeError('APPROVED_PATCH_NO_LONGER_APPLIES: '+check.stderr)
    run=subprocess.run(command,cwd=ROOT.parent,capture_output=True,text=True)
    if run.returncode:raise RuntimeError('APPROVED_PATCH_APPLICATION_FAILED: '+run.stderr)
    for name,digest in manifest['helper_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest
    assert sha(ROOT/'rag/qa.py')==prior['source_sha256']['rag/qa.py']
    assert (ROOT/'reports/assistant_backend_baseline/hashes.json').read_bytes()==(ROOT/'.scratch/institution-v2o3/before/reports/assistant_backend_baseline/hashes.json').read_bytes()
    result={'applied_at':datetime.now(timezone.utc).isoformat(),'authorization':'Latest user explicitly approved both exact SHA256 patches and their narrowly scoped exceptions.',
        'patches':{key:{'path':name,'sha256':digest} for key,(name,digest) in EXPECTED.items()},
        'preimages_exactly_matched_reviewed_O3':True,'combined_apply_check':True,'combined_git_apply_exit':run.returncode,
        'command':command,'actual_tree_applied':True,'protected_RAG_implementation_unchanged':True,'original_manifest_unchanged':True,
        'existing_files_modified':['tests/institution_v2j/test_diagnostics.py','tests/test_assistant_backend.py'],'new_approved_helpers':additions,
        'notes':'Exact approved patch retains historical proposal-status text in its test-only manifest/comment. Approval is recorded here; those approved bytes were not edited to relabel them.'}
    record.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'applied':True,'patches_verified':2,'protected_RAG_implementation_unchanged':True,'original_manifest_unchanged':True}))


if __name__=='__main__':main()
