"""All installed-guard mutants, including JSX and compiler comment directives."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
# Preserve the entire audited mutation corpus. Switch only its source snapshot
# and probe to the real installed guards/helpers. No candidate source is used.
source=(ROOT/'tests/institution_v2o2/test_contract_mutations.py').read_text().replace('v2o2','v2o3')
source=source.replace('rag_grounding_v2o3','rag_grounding_v2o2')
source=source.replace("CAND=ROOT/'.scratch/institution-v2o3/candidate/LibraryLLM'",'CAND=ROOT')
source=source.replace('institution_v2o3_guard_probe.py','institution_v2o3_closure_guard_probe.py')
exec(compile(source,str(ROOT/'tests/institution_v2o2/test_contract_mutations.py'),'exec'))
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
