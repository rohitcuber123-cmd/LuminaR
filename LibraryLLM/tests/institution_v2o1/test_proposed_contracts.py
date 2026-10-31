"""Candidate contract mutation checks; no patch is applied to frozen targets."""
import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'.scratch/institution-v2o1/proposed/tests/contracts'


def load(name):
    spec=importlib.util.spec_from_file_location('review_'+name,STAGE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_proposed_staff_contract_accepts_current_ux():
    load('staff_intelligence_v2o1').assert_staff_contract(ROOT)


@pytest.mark.parametrize('change', ['operator_fetch','foreign_scope','automatic_command','shell_import','raw_fence','transport_endpoint'])
def test_proposed_staff_contract_rejects_unauthorized_mutations(tmp_path,change):
    page=tmp_path/'frontend/src/pages/LibraryIntelligence.tsx';page.parent.mkdir(parents=True)
    helper=tmp_path/'frontend/src/lib/libraryIntelligence.ts';helper.parent.mkdir(parents=True)
    source=(ROOT/'frontend/src/pages/LibraryIntelligence.tsx').read_text();transport=(ROOT/'frontend/src/lib/libraryIntelligence.ts').read_text()
    if change=='operator_fetch':source+="\nvoid fetch('/operator/diagnostics')\n"
    elif change=='foreign_scope':source=source.replace('intelligenceStatus(id,controller.signal)',"intelligenceStatus('foreign',controller.signal)")
    elif change=='automatic_command':source+="\nvoid requestIntelligenceBuild(id,'SEARCH_INDEX')\n"
    elif change=='shell_import':source+="\nimport {exec} from 'node:child_process'\n"
    elif change=='raw_fence':source+="\nconst leaked = target.fence_token\n"
    elif change=='transport_endpoint':transport=transport.replace('/intelligence/builds','/intelligence/recover')
    page.write_text(source);helper.write_text(transport)
    with pytest.raises(AssertionError):load('staff_intelligence_v2o1').assert_staff_contract(tmp_path,compiler_root=ROOT)


def test_proposed_rag_contract_preserves_exact_original_frozen_projection():
    helper=load('rag_grounding_v2o1')
    original=(ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes()
    assert helper.reviewed_rag_payload((ROOT/'rag/qa.py').read_bytes())==original
    assert helper.reviewed_rag_payload(original)==original


@pytest.mark.parametrize('kind',['prompt','retrieval','citation','grounding','whitespace'])
def test_proposed_rag_contract_rejects_unreviewed_bytes(kind):
    data=(ROOT/'rag/qa.py').read_bytes()
    replacements={
        'prompt':(b'ANSWER:',b'ANSWER WITHOUT EVIDENCE:'),
        'retrieval':(b'select_definition_evidence(question, results, document_id, max_chunks)',b'select_definition_evidence(question, results, None, max_chunks)'),
        'citation':(b'([] if is_document and verdict == "NOT_SUPPORTED" else used_items)',b'used_items'),
        'grounding':(b'if is_document:',b'if False:'),
        'whitespace':(b'from rag.book_assets import valid_work_id',b'from rag.book_assets import valid_work_id '),
    }
    before,after=replacements[kind]
    assert before in data
    changed=data.replace(before,after,1)
    assert changed!=data
    with pytest.raises(AssertionError):load('rag_grounding_v2o1').reviewed_rag_payload(changed)
