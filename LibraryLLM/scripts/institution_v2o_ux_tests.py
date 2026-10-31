"""Generate only new O tests using accepted UI fixture scaffolding, not old tests."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
header=(ROOT/'frontend/tests/institution-intelligence-controls.test.tsx').read_text(encoding='utf8').split('for(const key')[0]
extra=r'''
const {stageProgress}=await import('../src/lib/libraryIntelligence')
for(const [current,total] of [[-1,10],[11,10],[1,0],[NaN,10],[1,Infinity],[1.5,10]])test(`invalid counter ${current}/${total} is indeterminate`,async()=>{
  value.search.current_job={...job(),progress_current:current,progress_total:total};await ready()
  assert.equal(stageProgress(value.search.current_job),null)
  assert.equal(screen.getByRole('progressbar').hasAttribute('value'),false)
})
test('stage100 is not publication completion',async()=>{value.search.current_job={...job('PUBLISHING'),progress_current:10,progress_total:10};await ready();assert.ok(screen.getByText(/Completion requires validated publication/));assert.equal(screen.queryByText('Succeeded'),null);assert.equal(stageProgress(value.search.current_job)?.percent,100)})
test('attempt history and durable timestamp are distinct from activity',async()=>{value.search.current_job={...job(),heartbeat_at:'2026-10-30T12:00:00Z'};value.search.latest_job={...job(),created_at:'2026-10-30T11:00:00Z'};await ready();assert.ok(screen.getByText(/Last durable job heartbeat:/));assert.equal(screen.getAllByText(/Worker activity/).length,2);assert.equal(document.body.textContent!.includes('healthy'),false)})
test('unverified retained pointer is not represented as validated',async()=>{value.search.active_generation_id='retained';value.search.artifact_verified=false;value.search.latest_job=job('FAILED');await ready();assert.ok(screen.getByText(/artifact validation is not confirmed/));assert.equal(screen.queryByText(/previous validated generation is retained/),null)})
test('invalid date does not crash status',async()=>{value.search.built_at='invalid-date';await ready();assert.ok(screen.getByText('Unavailable'))})
test('general user focus never fetches status',async()=>{institutions.setState({libraries:[library(a,'GENERAL_USER')] as any});page();fireEvent.focus(window);await act(async()=>Promise.resolve());assert.equal(calls.length,0)})
test('role revocation clears mounted status',async()=>{await ready();await act(async()=>institutions.setState({libraries:[library(a,'GENERAL_USER')] as any}));assert.equal(screen.queryByRole('heading',{name:'Semantic Search Index'}),null);assert.ok(screen.getByText('Staff membership required'))})
test('network failure removes build actions',async()=>{globalThis.fetch=async()=>{throw new TypeError('offline')};page();await screen.findByText('Status unavailable');assert.equal(screen.queryByRole('button',{name:'Build Search Index'}),null)})
test('503 retries are bounded',async()=>{let requests=0;globalThis.fetch=async()=>{requests++;return Response.json({detail:'wait'},{status:503})};page();await screen.findByText('Status unavailable',{}, {timeout:4000});assert.equal(requests,3);await act(async()=>new Promise(r=>setTimeout(r,1100)));assert.equal(requests,3)})
test('hidden tab stops polling, visible tab revalidates',async()=>{value.search.current_job=job();await ready();const before=calls.length;Object.defineProperty(document,'visibilityState',{value:'hidden',configurable:true});fireEvent(document,new Event('visibilitychange'));await act(async()=>new Promise(r=>setTimeout(r,3200)));assert.equal(calls.length,before);Object.defineProperty(document,'visibilityState',{value:'visible',configurable:true});fireEvent(document,new Event('visibilitychange'));await waitFor(()=>assert.ok(calls.length>before))})
test('logout clears old status response',async()=>{delayA=true;page();await waitFor(()=>assert.ok(resolveA));await act(async()=>{localStorage.removeItem('luminar_token');auth.setState({token:null,isAuthenticated:false});institutions.setState({libraries:[]})});await act(async()=>resolveA(Response.json(value)));assert.equal(screen.queryByRole('heading',{name:'Semantic Search Index'}),null)})
'''
(ROOT/'frontend/tests/institution-v2o-intelligence.test.tsx').write_text(header+extra,encoding='utf8')
