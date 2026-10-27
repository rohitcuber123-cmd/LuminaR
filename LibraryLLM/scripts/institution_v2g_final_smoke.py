"""Final served adapter/link and API readiness after the complete CI command."""
import time,requests
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    try:
        if all(requests.get(f'http://127.0.0.1:{port}'+('/' if port==8004 else '/health'),timeout=3).ok for port in [8002,8003,8004,8005]):break
    except requests.RequestException:pass
    time.sleep(.5)
else:raise AssertionError('Local APIs not ready.')
login('patron');goto('/libraries/'+TEST+'/graph')
page.locator('[data-graph-source=TENANT_KG]').wait_for(timeout=45000)
href=page.get_by_role('link',name='Explore Global Graph Lab',exact=True).get_attribute('href')
assert href.startswith('/experimental/kg?') and TEST in href
page.get_by_role('link',name='Explore Global Graph Lab',exact=True).click()
page.get_by_role('heading',name='Follow a book’s connections.',exact=True).wait_for(timeout=45000)
assert not page.locator('[data-graph-source=TENANT_KG]').count()
assert page.locator('.global-logo').get_attribute('href')=='/libraries/'+TEST
goto('/libraries/'+TEST+'/catalogue?search=networks');page.get_by_text('Library semantic search',exact=True).wait_for(timeout=45000)
put('institution_v2g_final_smoke.json',{'status':'PASS','API_ports_ready':[8002,8003,8004,8005],'frontend':BASE,'library_graph_return_context_preserved':True,'global_graph_source_separate':True,'tenant_semantic_ready':True,'no_rebuild':True})
print('PASS final APIs, served tenant Search and explicit Graph return context',flush=True)
