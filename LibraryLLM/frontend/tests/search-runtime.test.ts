import assert from 'node:assert/strict'
import { beforeEach, afterEach, test } from 'node:test'
import { JSDOM } from 'jsdom'
const dom=new JSDOM('',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage})
const {loadCatalogue}=await import('../src/lib/libraryCatalogue')
const {searchBooks}=await import('../src/lib/api')
const id='11111111-1111-4111-8111-111111111111'
const source={library_id:id,library_name:'QA',catalogue_source:'LIBRARY_LOCAL',local_book_count:1,capabilities:{},circulation_state:'CANONICAL'}
const original=globalThis.fetch
let calls:{path:string;init?:RequestInit}[]=[],state='READY',failure=0
beforeEach(()=>{
  calls=[];state='READY';failure=0;localStorage.setItem('luminar_token','qa-session')
  globalThis.fetch=async(input,init)=>{
    const path=String(input);calls.push({path,init})
    if(path.includes('/catalogue/search')&&failure)return Response.json({detail:'QA failure'},{status:failure})
    if(path.includes('/catalogue/'))return Response.json({source:{...source,search_source:state==='READY'?'TENANT_SEMANTIC':'LOCAL_FALLBACK',intelligence_status:state},results:[],total:0,offset:0,limit:20,has_more:false})
    return Response.json({results:[],total_ranked_candidates:0,has_more:false})
  }
})
afterEach(()=>{globalThis.fetch=original})
for(const staff of [false,true])test(`test_${staff?'staff':'patron'}_catalogue_discovery_uses_semantic_endpoint`,async()=>{
  await loadCatalogue('books',id,'search=beginner+computer+networking',new AbortController().signal,staff)
  assert.ok(calls[0].path.startsWith(`/search-api/libraries/${id}/catalogue/search?`))
  assert.equal(new URL(calls[0].path,'http://localhost').searchParams.get('staff'),staff?'true':null)
  assert.equal(calls.some(c=>c.path.includes('/catalogue/books')),false)
})
for(const staff of [false,true])test(`test_${staff?'staff':'patron'}_view_all_query_does_not_bypass_hnsw`,async()=>{
  await loadCatalogue('books',id,'view=for-you&search=community+memories',new AbortController().signal,staff)
  assert.ok(calls[0].path.startsWith(`/search-api/libraries/${id}/catalogue/search?`))
  assert.equal(calls.some(c=>c.path.includes('/recommendation')),false)
})
for(const stateValue of ['NOT_BUILT','BUILDING','FAILED','STALE'])test(`test_frontend_accepts_${stateValue}_local_fallback_without_global_filler`,async()=>{
  state=stateValue;const page=await loadCatalogue('books',id,'search=networking',new AbortController().signal) as any
  assert.equal(page.source.search_source,'LOCAL_FALLBACK');assert.equal(calls.length,1)
  assert.equal(calls.some(c=>c.path==='/search-api/search'),false)
})
test('test_blank_catalogue_query_retains_deterministic_browse',async()=>{
  await loadCatalogue('books',id,'subject=Networks',new AbortController().signal,true)
  assert.ok(calls[0].path.startsWith(`/api/libraries/${id}/catalogue/books?`))
})
test('test_empty_patron_view_all_query_uses_explicit_global_semantic_fallback',async()=>{
  const previous=globalThis.fetch
  globalThis.fetch=async(input,init)=>{
    const path=String(input)
    if(path.includes('/catalogue/search')){
      calls.push({path,init});return Response.json({source:{...source,catalogue_source:'GLOBAL_FALLBACK',local_book_count:0},results:[]})
    }
    return previous(input,init)
  }
  await loadCatalogue('books',id,'view=for-you&search=community+memories',new AbortController().signal)
  assert.ok(calls.some(c=>c.path==='/search-api/search'))
  assert.equal(calls.some(c=>c.path.includes('/recommendation')),false)
})
test('test_semantic_endpoint_preserves_exact_filters_and_pagination',async()=>{
  await loadCatalogue('books',id,'search=Campus+Network+Practice+Workbook&subject=Networks&author=QA&circulation_status=REFERENCE_ONLY&offset=20',new AbortController().signal,true)
  const params=new URL(calls[0].path,'http://localhost').searchParams
  assert.equal(params.get('subject'),'Networks');assert.equal(params.get('author'),'QA')
  assert.equal(params.get('circulation_status'),'REFERENCE_ONLY');assert.equal(params.get('offset'),'20')
})
test('test_search_service_failure_uses_tenant_core_fallback',async()=>{
  failure=502;const page=await loadCatalogue('books',id,'search=Networks',new AbortController().signal,true) as any
  assert.equal(calls.length,2);assert.ok(calls[1].path.startsWith(`/api/libraries/${id}/catalogue/discovery?`))
  assert.equal(page.source.search_source,'LOCAL_FALLBACK');assert.equal(page.source.intelligence_status,'UNAVAILABLE')
})
test('test_search_authority_failure_does_not_fall_through',async()=>{
  failure=403;await assert.rejects(loadCatalogue('books',id,'search=Networks',new AbortController().signal,true))
  assert.equal(calls.filter(c=>c.path.includes('/catalogue/')).length,1)
  assert.equal(calls.some(c=>c.path.includes('/catalogue/discovery')),false)
  assert.ok(calls[1].path.endsWith('/context'))
})
test('test_explicit_global_search_uses_global_semantic_endpoint',async()=>{
  await searchBooks('wizard boarding school adventures',10,'LIB001',false,false)
  assert.equal(calls[0].path,'/search-api/search')
  assert.equal(JSON.parse(calls[0].init!.body as string).query,'wizard boarding school adventures')
  assert.equal(calls.some(c=>c.path.includes('/libraries/')),false)
})
test('test_cancelled_tenant_search_never_uses_lexical_fallback',async()=>{
  const control=new AbortController();control.abort()
  await assert.rejects(loadCatalogue('books',id,'search=Networks',control.signal,true))
  assert.equal(calls.length,0)
})
