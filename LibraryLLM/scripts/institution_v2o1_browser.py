"""Fresh real Chromium regression, adding explicitly controlled denominator states."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
wrapper=(ROOT/'scripts/institution_v2o_browser.py').read_text().replace('v2o','v2o1')
marker="                exec(compile(source,str(ROOT/'scripts/institution_v2i_browser.py'),'exec'),"
assert marker in wrapper
old="                store.progress(claimed, 'EMBEDDING', 1, 3)"
new="""                store.progress(claimed, 'EMBEDDING', 0, 0)
                refresh(admin)
                expect(admin.get_by_role('progressbar', name='Search Index build progress')).not_to_have_attribute('value', '0')
                assert admin.get_by_role('progressbar', name='Search Index build progress').get_attribute('value') is None
                passed('CONTROLLED_DURABLE_STATE Search unknown denominator is indeterminate', observation_kind='Fixture store.progress, not native stage timing')
                store.progress(claimed, 'EMBEDDING', 1, 3)"""
refresh_marker="                passed('Active polling displays durable progress, no fake counter')"
refresh_extra="""                admin.reload()
                expect(admin.get_by_role('progressbar', name='Search Index build progress')).to_have_attribute('value', '2', timeout=30000)
                passed('Browser reload during controlled active build restores durable counters', observation_kind='Controlled durable stage; actual browser/backend')"""
kg_marker="                librarian = page_for(2)"
kg_extra="""                kg_request = api(f'/libraries/{a}/intelligence/builds','POST',{'target':'KNOWLEDGE_GRAPH'},expected=202)
                kg_claim = store.claim('owned-kg-progress-fixture')
                assert kg_claim['target']=='KNOWLEDGE_GRAPH'
                store.progress(kg_claim,'KG_METADATA',0,0)
                refresh(admin)
                expect(admin.get_by_role('progressbar',name='Knowledge Graph build progress')).to_be_visible()
                assert admin.get_by_role('progressbar',name='Knowledge Graph build progress').get_attribute('value') is None
                store.progress(kg_claim,'KG_METADATA',2,3)
                refresh(admin)
                expect(admin.get_by_role('progressbar',name='Knowledge Graph build progress')).to_have_attribute('value','2')
                passed('CONTROLLED_DURABLE_STATE KG building and unknown/known total', observation_kind='Fixture claim/progress, not native stage timing')
                repo.collection('intelligence_jobs').update_one({'job_id':kg_request['job_id']},{'$set':{'lease_expires_at':store.now()-timedelta(seconds=1)}})
                api(f'/libraries/{a}/intelligence/jobs/{kg_request["job_id"]}/recover','POST')
                api(f'/libraries/{a}/intelligence/builds','POST',{'target':'KNOWLEDGE_GRAPH'},expected=202)
                assert worker.run_one()
                refresh(admin)
                passed('Explicit manual native KG build after controlled fixture recovery validates publication')
                librarian = page_for(2)"""
insert=("                source=source.replace("+repr(old)+","+repr(new)+")\n"+
        "                source=source.replace("+repr(refresh_marker)+","+repr(refresh_marker+'\n'+refresh_extra)+")\n"+
        "                source=source.replace("+repr(kg_marker)+","+repr(kg_extra)+")\n")
wrapper=wrapper.replace(marker,insert+marker)
exec(compile(wrapper,str(ROOT/'scripts/institution_v2o_browser.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
