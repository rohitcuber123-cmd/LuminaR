"""Actual proposed frozen-test enforcement against isolated source mutations."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
CAND=ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'
PAGE='frontend/src/pages/LibraryIntelligence.tsx'
TRANSPORT='frontend/src/lib/libraryIntelligence.ts'
JFILES=[PAGE,TRANSPORT,'frontend/src/lib/institutions.ts','frontend/src/lib/api.ts',
        'backend/services/library_intelligence_service.py','backend/services/library_intelligence_store.py','backend/routes/library_intelligence.py']
JFILES += ['tests/contracts/staff_boundary_v2o2.'+ext for ext in ('py','cjs','json')]
JFILES += ['reports/institution_v2j_baseline.json']
RFILES=['rag/qa.py','rag/llm.py','rag/retriever.py','rag/reranker.py','rag/services/document_service.py',
        'reports/assistant_backend_baseline/hashes.json','tests/contracts/rag_grounding_v2o2.py']


def fixture(tmp_path,names):
    for name in names:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(CAND/name,p)
    return tmp_path


def probe(kind,root):
    p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2o2_guard_probe.py'),kind,str(root)],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert p.returncode in {0,2},p.stdout+p.stderr
    return json.loads(p.stdout)


def change(root,name,old,new):
    path=root/name;data=path.read_bytes();assert old in data,(name,old)
    path.write_bytes(data.replace(old,new,1))


@pytest.mark.parametrize('positive',['accepted_O','copy_edit','passive_layout','formatting'])
def test_proposed_J_guard_accepts_functional_presentation_evolution(tmp_path,positive):
    root=fixture(tmp_path,JFILES)
    if positive=='copy_edit':change(root,PAGE,b'Latest build attempt: Build failed.',b'Latest build attempt did not succeed.')
    elif positive=='passive_layout':change(root,PAGE,b'<h2 id=',b'<article><h2 id=');change(root,PAGE,b'</h2>',b'</h2></article>')
    elif positive=='formatting':
        p=root/PAGE;p.write_bytes(p.read_bytes().replace(b'const role =',b'const  role  ='))
    assert probe('j',root)['accepted']


MUTATIONS=['transport_body','transport_multiline_body','transport_dependency','generic_request_dependency',
           'bypass_status_helper','computed_fetch','escaped_fetch','generated_fetch','global_window','indirect_reference',
           'destructured_alias','aliased_import','namespace_import','dynamic_import','reexport','commonjs',
           'alternate_transport','selected_uuid','foreign_library','alternate_context','operator_endpoint',
           'automatic_build','indirect_build','replace_build_requester','worker_fence','computed_worker_fence',
           'backend_authority','librarian_readonly','librarian_card_guard','raw_credentials','shell_process',
           'jsx_expression_injection','html_network_tag','compiler_pragma','bundler_annotation','helper_tamper','manifest_tamper']


@pytest.mark.parametrize('mutation',MUTATIONS)
def test_proposed_J_guard_rejects_security_mutation(tmp_path,mutation):
    root=fixture(tmp_path,JFILES)
    if mutation=='transport_body':change(root,TRANSPORT,b"'GET', undefined, signal",b"'POST', {operator:true}, signal")
    elif mutation=='transport_multiline_body':change(root,TRANSPORT,b"=> institutionApi<IntelligenceStatus>(`/libraries/${id}/intelligence`, 'GET', undefined, signal)",b"=> {\n return institutionApi<IntelligenceStatus>('/operator/diagnostics', 'GET', undefined, signal)\n}")
    elif mutation=='transport_dependency':change(root,'frontend/src/lib/institutions.ts',b'apiPrefix + path',b"'/operator/diagnostics'")
    elif mutation=='generic_request_dependency':change(root,'frontend/src/lib/api.ts',b"const CORE_API = '/api'",b"const CORE_API = '/operator'")
    elif mutation=='bypass_status_helper':change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b"await fetch('/operator/diagnostics').then(r=>r.json())")
    elif mutation=='computed_fetch':change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b"await globalThis['fetch']('/operator/diagnostics')")
    elif mutation=='escaped_fetch':change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b"await window['f\\u0065tch']('/operator/diagnostics')")
    elif mutation=='generated_fetch':change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b"await globalThis[['fe','tch'].join('')]('/operator/diagnostics')")
    elif mutation=='global_window':change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b"await window.navigator.sendBeacon('/operator',id)")
    elif mutation=='indirect_reference':change(root,PAGE,b'const value = await intelligenceStatus',b'const send = intelligenceStatus; const value = await send')
    elif mutation=='destructured_alias':change(root,PAGE,b'const value = await intelligenceStatus(id,controller.signal)',b"const {fetch:send} = globalThis; const value = await send('/operator')")
    elif mutation=='aliased_import':
        change(root,PAGE,b'activeBuild, stageProgress, intelligenceStatus,',b'activeBuild, stageProgress, intelligenceStatus as readStatus,')
        change(root,PAGE,b'await intelligenceStatus(id,controller.signal)',b'await readStatus(id,controller.signal)')
    elif mutation=='namespace_import':
        change(root,PAGE,b"import { useParams } from 'react-router-dom'",b"import * as router from 'react-router-dom'")
        change(root,PAGE,b'useParams()',b'router.useParams()')
    elif mutation=='dynamic_import':change(root,PAGE,b'const role = libraryRole',b"void import('../lib/api'); const role = libraryRole")
    elif mutation=='reexport':change(root,PAGE,b"import './LibraryIntelligence.css'",b"import './LibraryIntelligence.css'; export * from '../lib/api'")
    elif mutation=='commonjs':change(root,PAGE,b'const role = libraryRole',b"const api = require('../lib/api'); const role = libraryRole")
    elif mutation=='alternate_transport':change(root,PAGE,b"from '../lib/libraryIntelligence'",b"from '../lib/api'")
    elif mutation=='selected_uuid':change(root,PAGE,b'id={libraryId}',b'id={"11111111-1111-4111-8111-111111111111"}')
    elif mutation=='foreign_library':change(root,PAGE,b'intelligenceStatus(id,controller.signal)',b'intelligenceStatus("11111111-1111-4111-8111-111111111111",controller.signal)')
    elif mutation=='alternate_context':change(root,PAGE,b"const { libraryId = '' } = useParams()",b"const libraryId = useInstitutionStore(s=>s.patronLibraryId)")
    elif mutation=='operator_endpoint':change(root,TRANSPORT,b'/libraries/${id}/intelligence`',b'/operator/diagnostics`')
    elif mutation=='automatic_build':change(root,PAGE,b'if (allowed) void load()',b'if (allowed) { void load(); void build() }')
    elif mutation=='indirect_build':change(root,PAGE,b'if (allowed) void load()',b'const start=build; if (allowed) { void load(); void start() }')
    elif mutation=='replace_build_requester':change(root,PAGE,b'await requestIntelligenceBuild(id,target.target,buildController.current?.signal)',b"await fetch('/operator/build',{method:'POST'})")
    elif mutation=='worker_fence':change(root,PAGE,b'{date(job.heartbeat_at)}',b'{job.fence_token}')
    elif mutation=='computed_worker_fence':change(root,PAGE,b'{date(job.heartbeat_at)}',b"{job['fence_'+'token']}")
    elif mutation=='backend_authority':change(root,'backend/services/library_intelligence_service.py',b"'can_build':member['role']=='ADMIN'",b"'can_build':True")
    elif mutation=='librarian_readonly':change(root,PAGE,b"admin={role === 'ADMIN'}",b'admin={true}')
    elif mutation=='librarian_card_guard':change(root,PAGE,b'{admin && data.can_build &&',b'{data.can_build &&')
    elif mutation=='raw_credentials':change(root,PAGE,b'{date(job.heartbeat_at)}',b"{localStorage.getItem('MONGO_URI')}")
    elif mutation=='shell_process':change(root,PAGE,b'const role = libraryRole',b"const shell = globalThis['require']('node:child_process'); shell.exec('cmd.exe'); const role = libraryRole")
    elif mutation=='jsx_expression_injection':change(root,PAGE,b'Latest build attempt: Build failed.',b"{(window['fetch']('/operator'), 'Build failed')}")
    elif mutation=='html_network_tag':change(root,PAGE,b'<h2 id=',b'<iframe id=');change(root,PAGE,b'</h2>',b'</iframe>')
    elif mutation=='compiler_pragma':
        p=root/PAGE;p.write_bytes(b'/** @jsx evilFactory */\n'+p.read_bytes())
    elif mutation=='bundler_annotation':change(root,PAGE,b'  useEffect(() =>',b'  /* @__PURE__ */ useEffect(() =>')
    elif mutation=='helper_tamper':
        p=root/'tests/contracts/staff_boundary_v2o2.py';p.write_bytes(p.read_bytes()+b'\n# unreviewed helper\n')
    elif mutation=='manifest_tamper':
        p=root/'tests/contracts/staff_boundary_v2o2.json';p.write_bytes(p.read_bytes()+b' ')
    assert not probe('j',root)['accepted'],mutation


@pytest.mark.parametrize('version',['reviewed_committed','original_frozen'])
def test_proposed_RAG_guard_accepts_only_reviewed_versions(tmp_path,version):
    root=fixture(tmp_path,RFILES)
    if version=='original_frozen':(root/'rag/qa.py').write_bytes((ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes())
    assert probe('rag',root)['accepted']


@pytest.mark.parametrize('mutation',['prompt','retrieval','citation','grounding','ownership_identity','whitespace','newline_only','third_historical_version','manifest','other_protected_file','helper'])
def test_proposed_RAG_guard_rejects_third_versions_and_rebasing(tmp_path,mutation):
    root=fixture(tmp_path,RFILES)
    replacements={'prompt':(b'ANSWER:',b'ANSWER WITHOUT EVIDENCE:'),
                  'retrieval':(b'select_definition_evidence(question, results, document_id, max_chunks)',b'select_definition_evidence(question, results, None, max_chunks)'),
                  'citation':(b'([] if is_document and verdict == "NOT_SUPPORTED" else used_items)',b'used_items'),
                  'grounding':(b'if is_document:',b'if False:'),
                  'ownership_identity':(b'not valid_work_id(document_id)',b'valid_work_id(document_id)')}
    if mutation in replacements:change(root,'rag/qa.py',*replacements[mutation])
    elif mutation=='whitespace':
        p=root/'rag/qa.py';p.write_bytes(p.read_bytes()+b' ')
    elif mutation=='newline_only':
        p=root/'rag/qa.py';p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))
    elif mutation=='third_historical_version':
        p=root/'rag/qa.py';p.write_bytes((ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes()+b'\n')
    elif mutation=='manifest':
        p=root/'reports/assistant_backend_baseline/hashes.json';data=json.loads(p.read_text(encoding='utf-8-sig'));data[2]['Hash']='0'*64;p.write_text(json.dumps(data))
    elif mutation=='other_protected_file':
        p=root/'rag/llm.py';p.write_bytes(p.read_bytes()+b'\n# unreviewed\n')
    elif mutation=='helper':
        p=root/'tests/contracts/rag_grounding_v2o2.py';p.write_bytes(p.read_bytes()+b'\n# unreviewed\n')
    assert not probe('rag',root)['accepted'],mutation
