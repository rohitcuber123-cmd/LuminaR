"""Produce reviewable protected-test diffs; never apply them to the workspace."""
import difflib,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';STAGE=ROOT/'.scratch/institution-v2o1/proposed'


def main():
    transport=lambda text:'\n'.join(line for line in text.splitlines() if line.startswith(('export const activeBuild =','export const intelligenceStatus =','export const requestIntelligenceBuild =')))+'\n'
    lib=(ROOT/'frontend/src/lib/libraryIntelligence.ts').read_text()
    old=(ROOT/'.scratch/institution-v2o/before/frontend/src/lib/libraryIntelligence.ts').read_text()
    assert transport(lib)==transport(old)
    digest=hashlib.sha256(transport(lib).encode()).hexdigest()
    analyzer=r'''// Proposed reviewed test-only AST boundary; never executes application code.
const fs=require('node:fs'),path=require('node:path');
const ts=require(process.argv[3]);
const source=ts.createSourceFile('LibraryIntelligence.tsx',fs.readFileSync(process.argv[2],'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
const allowed=new Set(['react','react-router-dom','../components/WorkspaceUI','../components/StaffUI','../store/useAuthStore','../store/useInstitutionStore','../lib/libraryWorkspace','../lib/libraryIntelligence','./LibraryIntelligence.css']);
const forbidden=new Set(['fetch','XMLHttpRequest','WebSocket','EventSource','sendBeacon','eval','Function','require','exec','spawn','fence_token','worker_id','mongo_uri']);
const errors=[];let reads=0,commands=0;
function inspect(node){
 if(ts.isImportDeclaration(node)){
  if(!allowed.has(node.moduleSpecifier.text))errors.push('UNREVIEWED_IMPORT');
  const bindings=node.importClause?.namedBindings;
  if(bindings&&ts.isNamespaceImport(bindings))errors.push('NAMESPACE_IMPORT');
  if(bindings&&ts.isNamedImports(bindings)&&bindings.elements.some(x=>x.propertyName))errors.push('ALIASED_IMPORT');
 }
 if(ts.isIdentifier(node)&&forbidden.has(node.text))errors.push('FORBIDDEN_CAPABILITY');
 if(ts.isStringLiteralLike(node)&&(/mongodb(?:\+srv)?:\/\//i.test(node.text)||/^\/(?:operator|diagnostic)/i.test(node.text)||/powershell|cmd\.exe/i.test(node.text)))errors.push('INFRASTRUCTURE_LITERAL');
 if(ts.isCallExpression(node)){
  if(node.expression.kind===ts.SyntaxKind.ImportKeyword)errors.push('DYNAMIC_IMPORT');
  const name=ts.isIdentifier(node.expression)?node.expression.text:'';
  if(['intelligenceStatus','requestIntelligenceBuild'].includes(name)){
   if(!node.arguments[0]||!ts.isIdentifier(node.arguments[0])||node.arguments[0].text!=='id')errors.push('NONCANONICAL_SCOPE');
   if(name==='intelligenceStatus')reads++;
   else{commands++;let p=node.parent;while(p&&!ts.isFunctionDeclaration(p))p=p.parent;if(!p||p.name?.text!=='build')errors.push('COMMAND_OUTSIDE_EXPLICIT_ACTION');}
  }
 }
 ts.forEachChild(node,inspect);
}
inspect(source);
if(reads!==1||commands!==1)errors.push('TRANSPORT_SURFACE_CHANGED');
process.stdout.write(JSON.stringify({ok:errors.length===0,errors:[...new Set(errors)]}));
'''
    staff='''"""PROPOSED: reviewed transport fingerprint + AST boundary, alongside UI behavior tests."""
import hashlib,json,subprocess
from pathlib import Path

TRANSPORT_SHA256 = 'DIGEST'


def assert_staff_contract(root, *, compiler_root=None):
    root=Path(root)
    helper=(root/'frontend/src/lib/libraryIntelligence.ts').read_text(encoding='utf8')
    lines='\\n'.join(line for line in helper.splitlines() if line.startswith(('export const activeBuild =','export const intelligenceStatus =','export const requestIntelligenceBuild =')))+'\\n'
    assert hashlib.sha256(lines.encode()).hexdigest()==TRANSPORT_SHA256,'Reviewed tenant transport/active-state contract changed'
    compiler=Path(compiler_root or root)/'frontend/node_modules/typescript'
    analyzer=Path(__file__).with_suffix('.cjs')
    result=subprocess.run(['node',str(analyzer),str(root/'frontend/src/pages/LibraryIntelligence.tsx'),str(compiler)],capture_output=True,text=True,timeout=10,check=True)
    verdict=json.loads(result.stdout)
    assert verdict['ok'],verdict['errors']
'''.replace('DIGEST',digest)
    rag=r'''"""PROPOSED reviewed exception: exact current bytes AND exact old-source projection.

Original hashes.json stays unchanged. Unknown byte changes are rejected; this is
not a generic newline normalizer or an acceptance of arbitrary current source.
"""
import hashlib
LEGACY_SHA256='0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6'
REVIEWED_SHA256='4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3'


def reviewed_rag_payload(payload):
    actual=hashlib.sha256(payload).hexdigest()
    if actual==LEGACY_SHA256:return payload
    assert actual==REVIEWED_SHA256,'Unreviewed protected RAG bytes'
    additions=[b'from rag.book_assets import valid_work_id',b'from rag.document_grounding import select_definition_evidence, definition_category',
        b'        is_document = bool(document_id and not valid_work_id(document_id))',b'        if is_document:',
        b'            results = select_definition_evidence(question, results, document_id, max_chunks)',
        b'            q_category = definition_category(question, used_items, document_id) or q_category']
    lines=payload.splitlines(keepends=True)
    for line in additions:assert sum(item.rstrip(b'\r\n')==line for item in lines)==(2 if line==b'        if is_document:' else 1)
    lines=[line for line in lines if line.rstrip(b'\r\n') not in additions]
    revised=b'        for item in ([] if is_document and verdict == "NOT_SUPPORTED" else used_items):'
    assert sum(line.rstrip(b'\r\n')==revised for line in lines)==1
    original=b''.join(b'        for item in used_items:\r\n' if line.rstrip(b'\r\n')==revised else line for line in lines)
    assert hashlib.sha256(original).hexdigest()==LEGACY_SHA256,'Reviewed source delta does not project to frozen source'
    return original
'''
    files={'tests/contracts/staff_intelligence_v2o1.py':staff,'tests/contracts/staff_intelligence_v2o1.cjs':analyzer,'tests/contracts/rag_grounding_v2o1.py':rag}
    for name,content in files.items():
        p=STAGE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content,encoding='utf8')
    fingerprints={name:hashlib.sha256((STAGE/name).read_bytes()).hexdigest() for name in files}
    jpath='tests/institution_v2j/test_diagnostics.py';original=(ROOT/jpath).read_bytes().decode('utf8')
    proposal=original.replace("'backend/routes/library_intelligence.py','frontend/src/pages/LibraryIntelligence.tsx']:","'backend/routes/library_intelligence.py']:")
    marker='    # Part2L explicitly integrates the native worker.'
    insertion='    # Part2O frontend evolution: approved boundary + behavioral tests replace whole-page immutability.\n'
    for name in list(files)[:2]:insertion+=f"    assert hashlib.sha256((ROOT/{name!r}).read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=={fingerprints[name]!r}\n"
    insertion+='    from tests.contracts.staff_intelligence_v2o1 import assert_staff_contract\n    assert_staff_contract(ROOT)\n'
    proposal=proposal.replace(marker,insertion+marker);assert proposal!=original
    rpath='tests/test_assistant_backend.py';r_original=(ROOT/rpath).read_bytes().decode('utf8')
    old_assert="            assert hashlib.sha256(Path(row['Path']).read_bytes()).hexdigest().upper() == row['Hash']"
    r_new="            payload = Path(row['Path']).read_bytes()\n            if Path(row['Path']).name == 'qa.py':\n"
    r_new+=f"                assert hashlib.sha256((ROOT/'tests/contracts/rag_grounding_v2o1.py').read_bytes().replace(b'\\r\\n',b'\\n')).hexdigest()=={fingerprints['tests/contracts/rag_grounding_v2o1.py']!r}\n"
    r_new+="                from tests.contracts.rag_grounding_v2o1 import reviewed_rag_payload\n                payload = reviewed_rag_payload(payload)\n            assert hashlib.sha256(payload).hexdigest().upper() == row['Hash']"
    r_proposal=r_original.replace(old_assert,r_new);assert r_proposal!=r_original
    def patch(name,edits):
        text=''
        for path,before,after in edits:
            text+=f'diff --git a/LibraryLLM/{path} b/LibraryLLM/{path}\n'
            if not before:text+='new file mode 100644\n'
            text+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/LibraryLLM/'+path if before else '/dev/null',tofile='b/LibraryLLM/'+path))
        target=R/f'institution_v2o1_{name}_approval.patch';target.write_text(text,encoding='utf8')
        p=subprocess.run(['git','apply','--check','--ignore-space-change',str(target)],cwd=ROOT.parent,capture_output=True,text=True)
        assert p.returncode==0,p.stderr
        return {'path':str(target.relative_to(ROOT)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'git_apply_check':True,'check_option':'--ignore-space-change (Windows context line endings only)','applied':False}
    j=patch('j',[(jpath,original,proposal),*[(n,'',files[n]) for n in list(files)[:2]]])
    r=patch('rag',[(rpath,r_original,r_proposal),('tests/contracts/rag_grounding_v2o1.py','',rag)])
    (R/'institution_v2o1_approval_manifest.json').write_text(json.dumps({'status':'AWAITING_EXPLICIT_APPROVAL','J':j,'RAG':r,'helper_fingerprints':fingerprints,'original_hash_manifest_modified':False,'protected_targets_modified':False},indent=2))
    print(json.dumps({'patches_prepared':2,'git_apply_check':'PASS','applied':False}))


if __name__=='__main__':main()
