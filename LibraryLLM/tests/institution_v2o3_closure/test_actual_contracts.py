"""All installed-guard mutants, including JSX and compiler comment directives."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
# Preserve the entire audited mutation corpus. Switch only its source snapshot
# and probe to the real installed guards/helpers. No candidate source is used.
source=(ROOT/'tests/institution_v2o2/test_contract_mutations.py').read_text().replace('v2o2','v2o3')
source=source.replace('rag_grounding_v2o3','rag_grounding_v2o2')
source=source.replace("CAND=ROOT/'.scratch/institution-v2o3/candidate/LibraryLLM'",'CAND=ROOT')
source=source.replace('institution_v2o3_guard_probe.py','institution_v2o3_closure_guard_probe.py')
source=source.replace(
    'b\'([] if is_document and verdict == "NOT_SUPPORTED" else used_items)\'',
    'b\'([] if suppress_sources or (is_document and verdict == "NOT_SUPPORTED") else used_items)\'',
)
exec(compile(source,str(ROOT/'tests/institution_v2o2/test_contract_mutations.py'),'exec'))
RFILES += ['rag/fast_filter.py', 'rag/factual_evidence.py', 'rag/document_grounding.py',
           'rag/generated_answer_verification.py', 'rag/citation_boundary.py',
           'tests/contracts/rag_grounding_v2q.py']


@pytest.mark.parametrize('version,expected',[('reviewed_committed',True),('original_frozen',False)])
def test_proposed_RAG_guard_accepts_only_reviewed_versions(tmp_path,version,expected):
    root=fixture(tmp_path,RFILES)
    if version=='original_frozen':
        (root/'rag/qa.py').write_bytes((ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes())
    assert probe('rag',root)['accepted'] is expected


def test_historical_qa_projection_remains_frozen():
    import hashlib
    from tests.contracts.rag_grounding_v2o2 import reviewed_rag_payload
    old=(ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes()
    assert hashlib.sha256(reviewed_rag_payload(old)).hexdigest()=='0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6'


@pytest.mark.parametrize('relative,old,new',[
    ('rag/qa.py',b'answer = self.llm.generate(',b'answer = "unverified" if False else self.llm.generate('),
    ('rag/qa.py',b'selected_source_id=document_id or work_id',b'selected_source_id=None'),
    ('rag/llm.py',b'from rag.factual_evidence import',b'from rag.unreviewed import'),
    ('rag/fast_filter.py',b'"FAST_REJECT"',b'"FAST_ACCEPT"'),
    ('rag/factual_evidence.py',b'VERSION =',b'VERSION = "unreviewed" #'),
    ('rag/document_grounding.py',b'document_id',b'foreign_document_id'),
    ('rag/generated_answer_verification.py',b'if yes != supported:',b'if False:'),
    ('rag/citation_boundary.py',b'return False',b'return True'),
])
def test_reviewed_rag_guard_rejects_dependency_mutation(tmp_path,relative,old,new):
    root=fixture(tmp_path,RFILES)
    change(root,relative,old,new)
    assert not probe('rag',root)['accepted']


def test_reviewed_rag_guard_rejects_helper_mutation(tmp_path):
    root=fixture(tmp_path,RFILES)
    path=root/'tests/contracts/rag_grounding_v2q.py'
    path.write_bytes(path.read_bytes()+b'\n# unreviewed\n')
    assert not probe('rag',root)['accepted']
jsx=(ROOT/'tests/institution_v2o3/test_jsx_boundary.py').read_text()
jsx=jsx.replace('from tests.institution_v2o3.test_contract_mutations import JFILES,PAGE,change,fixture,probe','')
exec(compile(jsx,str(ROOT/'tests/institution_v2o3/test_jsx_boundary.py'),'exec'))


@pytest.mark.parametrize('directive',[
    '// @ts-ignore\n','// @ts-expect-error\n','// @ts-nocheck\n','// @ts-check\n',
    '/* @ts-ignore */\n','/* @ts-expect-error */\n','/* @ts-nocheck */\n','/** @jsxImportSource alternate */\n',
])
def test_installed_guard_rejects_compiler_affecting_comment_directive(tmp_path,directive):
    root=fixture(tmp_path,JFILES)
    page=root/PAGE;page.write_bytes(directive.encode()+page.read_bytes())
    result=probe('j',root)
    assert result['guard_source']=='installed_actual_tree'
    assert not result['accepted']
