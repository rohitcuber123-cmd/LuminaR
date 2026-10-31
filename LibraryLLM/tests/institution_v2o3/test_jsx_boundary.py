"""Native presentation exception excludes every custom component prop."""
import pytest
from tests.institution_v2o3.test_contract_mutations import JFILES,PAGE,change,fixture,probe


@pytest.mark.parametrize('prop',['className','title','aria-label','aria-describedby','htmlFor','id'])
def test_custom_component_literal_prop_never_ignored(tmp_path,prop):
    root=fixture(tmp_path,JFILES)
    if prop=='title':change(root,PAGE,b'<PageHeading title="Intelligence"',b'<PageHeading title="Unreviewed control"')
    else:change(root,PAGE,b'<PageHeading title="Intelligence"',f'<PageHeading {prop}="unreviewed" title="Intelligence"'.encode())
    assert not probe('j',root)['accepted']


@pytest.mark.parametrize('old,new',[(b'<button ',b'<span '),(b'<progress ',b'<div '),(b'<summary>',b'<p>')])
def test_interactive_and_semantic_native_tag_changes_are_protected(tmp_path,old,new):
    root=fixture(tmp_path,JFILES)
    change(root,PAGE,old,new)
    if old==b'<button ':change(root,PAGE,b'</button>',b'</span>')
    elif old==b'<summary>':change(root,PAGE,b'</summary>',b'</p>')
    assert not probe('j',root)['accepted']


def test_build_interaction_cannot_be_replaced_by_hover(tmp_path):
    root=fixture(tmp_path,JFILES)
    change(root,PAGE,b'onClick={onBuild}',b'onMouseEnter={onBuild}')
    assert not probe('j',root)['accepted']


def test_interactive_literal_presentation_props_are_not_exempt(tmp_path):
    root=fixture(tmp_path,JFILES)
    change(root,PAGE,b'<button className="secondary"',b'<button className="unreviewed"')
    assert not probe('j',root)['accepted']


@pytest.mark.parametrize('kind',['container_class','passive_tag'])
def test_reviewed_passive_native_presentation_remains_evolvable(tmp_path,kind):
    root=fixture(tmp_path,JFILES)
    if kind=='container_class':change(root,PAGE,b'className="ui-card intelligence-card"',b'className="ui-card revised-spacing"')
    else:
        change(root,PAGE,b'<section className=',b'<article className=')
        change(root,PAGE,b'</section>',b'</article>')
    assert probe('j',root)['accepted']
