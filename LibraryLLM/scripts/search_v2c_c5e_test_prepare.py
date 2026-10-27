"""Build C5E-only regression copies and disposable native qualification adapter."""
from pathlib import Path

ROOT=Path('scratch/search_v2c_c5e')
def main():
    old=Path('scratch/search_v2c_c5d_repair_v2')
    for p in old.rglob('test*.py'):
        dest=ROOT/p.relative_to(old);dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('x',encoding='utf8') as out:
            out.write(p.read_text(encoding='utf8').replace('scratch.search_v2c_c5d_repair_v2','scratch.search_v2c_c5e'))
    native=ROOT/'native';native.mkdir()
    conf=Path('tests/institution_v2g/conftest.py').read_text(encoding='utf8')
    conf=conf.replace('luminar_institution_v2g_test_','luminar_search_c5e_test_')
    conf=conf.replace("import fitz", "os.environ['LUMINAR_SESSION_DB'] = str(__import__('pathlib').Path('scratch/search_v2c_c5e/native/login_sessions.sqlite').resolve())\n\nimport fitz")
    conf+='''

@pytest.fixture(autouse=True)
def disabled_candidate_adapter(monkeypatch):
    # Test-process dependency substitution only. All native routing, guards,
    # membership checks, capabilities and one-use reservations stay unchanged.
    import search.query_session as sessions
    import search.session_store as store
    import search.query_interaction as interactions
    import search.query_execution as execution
    from scratch.search_v2c_c5e.candidate_search import query_plan as plans
    from scratch.search_v2c_c5e.candidate_search import query_confidence as decisions
    for module in [sessions,store,interactions,execution]:
        for name in ['parse_query','QueryPlan','FacetVocabulary','PARSER_VERSION']:
            if hasattr(module,name):monkeypatch.setattr(module,name,getattr(plans,name))
    for name in ['validate','decide']:
        monkeypatch.setattr(interactions,name,getattr(decisions,name))
'''
    (native/'conftest.py').write_text(conf,encoding='utf8')
    source=Path('tests/institution_v2g/test_query_v2c_c5a_native.py').read_text(encoding='utf8')
    source=source.replace('luminar_institution_v2g_test_','luminar_search_c5e_test_')
    (native/'test_native_contract.py').write_text(source,encoding='utf8')
    print('Created C5E-only regression and disposable native adapter copies.')
if __name__=='__main__':main()
