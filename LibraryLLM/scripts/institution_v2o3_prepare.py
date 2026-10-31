"""Audited JSX candidate and exact final patches; no working-tree application."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
OWN=ROOT/'.scratch/institution-v2o3';STAGE=OWN/'proposed';CAND=OWN/'candidate/LibraryLLM'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    old=json.loads((R/'institution_v2o2_approval_manifest.json').read_text())
    expected={'J':'b65e11352b78cb72d0a67686ae939635e5eaab9c3f544c36e214cfb20f94e0a0',
              'RAG':'76c09bfef7e676595e0af6974e55aa232e63c684ec51961c558eabf97e45431b'}
    for key,digest in expected.items():assert sha(ROOT/old[key]['path'])==digest==old[key]['sha256']
    base=json.loads((R/'institution_v2o3_baseline.json').read_text())
    page='frontend/src/pages/LibraryIntelligence.tsx'
    assert sha(ROOT/page)==base['source_sha256'][page]=='51f58263f2c06fda2bb3f6669de94a735af2d0b97e3cf4497bc154c1375adfd3'
    prior=json.loads((ROOT/'.scratch/institution-v2o2/proposed/tests/contracts/staff_boundary_v2o2.json').read_text())
    for name,digest in prior['full_transport_modules'].items():assert sha(ROOT/name)==digest
    for name,digest in prior['backend_authority'].items():assert sha(ROOT/name)==digest
    analyzer=(ROOT/'tests/institution_v2o2/candidate_templates/staff_boundary.cjs').read_text()
    original=analyzer
    analyzer=analyzer.replace("'dd','details','summary','label','progress','button','ul'", "'dd','ul'")
    marker="const presentationAttributes ="
    analyzer=analyzer.replace(marker,"const interactionTags = new Set(['details','summary','label','progress','button']);\n"+marker)
    analyzer=analyzer.replace("  const passive = /^[a-z]/.test(tag);\n  if (passive && !passiveTags.has(tag)) errors.push(`UNREVIEWED_HTML_CAPABILITY:${tag}`);",
        "  const native = /^[a-z]/.test(tag);\n  const passive = passiveTags.has(tag);\n  if (native && !passive && !interactionTags.has(tag)) errors.push(`UNREVIEWED_HTML_CAPABILITY:${tag}`);")
    analyzer=analyzer.replace('if (ts.isJsxAttribute(a) && presentationAttributes.has', 'if (passive && ts.isJsxAttribute(a) && presentationAttributes.has')
    assert analyzer!=original and 'if (passive && ts.isJsxAttribute(a)' in analyzer
    contract=STAGE/'tests/contracts/staff_boundary_v2o3';contract.parent.mkdir(parents=True,exist_ok=True)
    contract.with_suffix('.cjs').write_bytes(analyzer.encode())
    contract.with_suffix('.py').write_bytes((ROOT/'tests/institution_v2o2/candidate_templates/staff_boundary.py').read_bytes())
    observed=json.loads(subprocess.check_output(['node',str(contract.with_suffix('.cjs')),str(ROOT/page),str(ROOT/'frontend/node_modules/typescript')],text=True));assert observed['ok'],observed
    manifest={**prior,'schema':2,'page_executable_sections':observed['sections'],
              'boundary':'Only reviewed native passive tags ignore fixed literal presentation attributes. Custom component props and native interactive/semantic tags retain complete structure; executable code remains pinned.',
              'approval_status':'PROPOSED_AUDITED_REVISION_AWAITING_USER_APPROVAL'}
    contract.with_suffix('.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    files=['tests/contracts/staff_boundary_v2o3.'+ext for ext in ('py','cjs','json')]
    pins={name:hashlib.sha256((STAGE/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest() for name in files}
    jpath='tests/institution_v2j/test_diagnostics.py';original_test=(ROOT/jpath).read_text()
    proposed=original_test.replace("'backend/routes/library_intelligence.py','frontend/src/pages/LibraryIntelligence.tsx']:","'backend/routes/library_intelligence.py']:")
    extra='    # Proposed O.3 audited JSX boundary; separate user approval required.\n'
    for name in files:extra+=f"    assert hashlib.sha256((ROOT/{name!r}).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=={pins[name]!r}\n"
    extra+='    from tests.contracts.staff_boundary_v2o3 import assert_staff_contract\n    assert_staff_contract(ROOT)\n'
    proposed=proposed.replace('    # Part2L explicitly integrates the native worker.',extra+'    # Part2L explicitly integrates the native worker.')
    assert proposed!=original_test
    patch=''
    for name,before,after in [(jpath,original_test,proposed),*[(name,'',(STAGE/name).read_text()) for name in files]]:
        patch+=f'diff --git a/LibraryLLM/{name} b/LibraryLLM/{name}\n'
        if not before:patch+='new file mode 100644\n'
        patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/LibraryLLM/'+name if before else '/dev/null',tofile='b/LibraryLLM/'+name))
    jp=R/'institution_v2o3_j_approval.patch';jp.write_bytes(patch.replace('\r\n','\n').encode())
    rp=R/'institution_v2o3_rag_approval.patch';rp.write_bytes((ROOT/old['RAG']['path']).read_bytes())
    for p in (jp,rp):subprocess.run(['git','apply','--check','--ignore-space-change',str(p)],cwd=ROOT.parent,check=True)
    # Assertion text in a scratch fixture only. No git apply, install or actual
    # protected-test modification occurs. Guard probes compile its exact body.
    source_names=[page,*prior['full_transport_modules'],*prior['backend_authority'],
        'reports/institution_v2j_baseline.json','reports/assistant_backend_baseline/hashes.json',
        'rag/qa.py','rag/llm.py','rag/retriever.py','rag/reranker.py','rag/services/document_service.py']
    for name in set(source_names):
        p=CAND/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    for name in files:
        p=CAND/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STAGE/name,p)
    (CAND/jpath).parent.mkdir(parents=True,exist_ok=True);(CAND/jpath).write_bytes(proposed.encode())
    rname='tests/contracts/rag_grounding_v2o2.py'
    (CAND/rname).write_bytes((ROOT/'.scratch/institution-v2o2/proposed'/rname).read_bytes())
    (CAND/'tests/test_assistant_backend.py').write_bytes((ROOT/'.scratch/institution-v2o2/proposed/tests/test_assistant_backend.py').read_bytes())
    compiler=CAND/'frontend/node_modules/typescript'
    if not compiler.exists():shutil.copytree(ROOT/'frontend/node_modules/typescript',compiler)
    (R/'institution_v2o3_approval_manifest.json').write_text(json.dumps({'authorization':'NOT_RECEIVED','actual_tree_applied':False,
        'J':{'path':jp.relative_to(ROOT).as_posix(),'sha256':sha(jp),'supersedes':expected['J']},
        'RAG':{'path':rp.relative_to(ROOT).as_posix(),'sha256':sha(rp),'unchanged_from_O2':True},
        'helper_sha256':pins,'full_transport_modules':prior['full_transport_modules'],'backend_authority':prior['backend_authority'],
        'audited_candidate_manifest':manifest,'apply_check':'PASS','candidate_scope':'Only scratch assertion fixtures; no patch applied anywhere.'},indent=2)+'\n')
    print(json.dumps({'authorization':'NOT_RECEIVED','candidate_prepared':True,'actual_tree_applied':False,'J_sha256':sha(jp),'RAG_sha256':sha(rp)}))


if __name__=='__main__':main()
