import assert from 'node:assert/strict'
import {registerHooks} from 'node:module'
import {test,beforeEach,afterEach} from 'node:test'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,ctx,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,ctx)}})
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
Object.assign(globalThis,{ResizeObserver:class{observe(){}disconnect(){}}})
dom.window.HTMLElement.prototype.scrollTo=function(options:any){this.scrollLeft=options.left||0;this.dispatchEvent(new Event('scroll'))}
const {render,screen,fireEvent,waitFor,cleanup}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {ForYou}=await import('../src/components/ForYou')
const {HomeCatalogueContext}=await import('../src/components/HomeCatalogueContext')
const {libraryRecommendationPage}=await import('../src/lib/libraryCatalogue')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222'
const original=globalThis.fetch
let calls:string[]=[],unavailable=false
function source(id:string){return {library_id:id,library_name:id===a?'A':'B',catalogue_source:'LIBRARY_LOCAL',local_book_count:30,capabilities:{},circulation_state:'CANONICAL'}}
function rows(id:string){return Array.from({length:30},(_,i)=>({display_id:`${id}-${i}`,library_id:id,library_book_id:`${id}-${i}`,global_work_id:i===0?'OL1W':null,source:'LIBRARY',title:`${id===a?'A':'B'} Local ${i}`,authors:['QA'],subjects:['Networks'],owned_by_current_library:true,book_format:'PHYSICAL_ONLY',has_physical:true,actions:{},cover_seed:i}))}
function home(id:string):any{return {source:source(id),for_you:rows(id).slice(0,10),featured:[],new_arrivals:[],popular:[],subjects:[],my_library:{}}}
function renderRail(id=a){return render(<MemoryRouter initialEntries={[`/libraries/${id}`]}><HomeCatalogueContext.Provider value={{data:home(id),changed:()=>{}}}><ForYou/></HomeCatalogueContext.Provider></MemoryRouter>)}
beforeEach(()=>{
 cleanup();calls=[];unavailable=false;localStorage.clear();localStorage.setItem('luminar_token','qa-session')
 auth.setState({token:'qa-session',isAuthenticated:true,user:{user_id:1,name:'QA',email:'qa@example.com',role:'GENERAL_USER'} as any})
 institutions.setState({session:'qa-session',owner:'qa@example.com',patronLibraryId:a,activeId:a,staffLibraryId:null,loading:false,libraries:[a,b].map(id=>({library_id:id,name:id===a?'A':'B',membership:{role:'GENERAL_USER',status:'ACTIVE'}})) as any})
 globalThis.fetch=async(input)=>{
   const path=String(input);calls.push(path)
   if(path.startsWith('/recommendation-api/'))return unavailable?Response.json({detail:'Unavailable'},{status:503}):Response.json({recommendations:[{work_id:'OL1W',title:'Global signal'}]})
   if(path.includes('/catalogue/recommendations')){const id=path.includes(b)?b:a;return Response.json({source:source(id),results:rows(id),ranking:'GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY'})}
   return Response.json({results:[],books:[]})
 }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
test('test_tenant_recommendation_provider_traced',async()=>{
 await libraryRecommendationPage(a,new AbortController().signal)
 assert.equal(calls[0],'/recommendation-api/recommendations?limit=50&offset=0')
 assert.equal(calls[1],`/api/libraries/${a}/catalogue/recommendations`)
 assert.equal(calls.some(p=>p.includes('/catalogue/search')),false)
})
test('test_tenant_recommendations_library_scoped',async()=>{
 const page=await libraryRecommendationPage(a,new AbortController().signal)
 assert.equal(page.results.length,10);assert.ok(page.results.every(r=>r.library_id===a&&r.source==='LIBRARY'))
})
test('test_tenant_recommendations_no_global_filler',async()=>{
 unavailable=true;const page=await libraryRecommendationPage(a,new AbortController().signal)
 assert.ok(page.results.every(r=>r.source==='LIBRARY'));assert.equal(page.total,30)
})
test('test_recommendation_next_page_same_provider',async()=>{
 renderRail();await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Next Recommendations'}) as HTMLButtonElement).disabled,false))
 fireEvent.click(screen.getByRole('button',{name:'Next Recommendations'}));await screen.findAllByText('A Local 10')
 assert.ok(calls.filter(p=>p.includes('/catalogue/')).every(p=>p===`/api/libraries/${a}/catalogue/recommendations`))
 assert.equal(screen.queryByText('A Local 0'),null)
})
test('test_recommendation_previous_page_same_provider',async()=>{
 renderRail();await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Next Recommendations'}) as HTMLButtonElement).disabled,false))
 fireEvent.click(screen.getByRole('button',{name:'Next Recommendations'}));await screen.findAllByText('A Local 10')
 fireEvent.click(screen.getByRole('button',{name:'Previous Recommendations'}));await screen.findAllByText('A Local 0')
 assert.equal(screen.queryByText('A Local 10'),null)
})
test('test_recommendation_multi_library_isolation',async()=>{
 const view=renderRail();await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Next Recommendations'}) as HTMLButtonElement).disabled,false))
 fireEvent.click(screen.getByRole('button',{name:'Next Recommendations'}));await screen.findAllByText('A Local 10')
 institutions.setState({patronLibraryId:b,activeId:b})
 view.rerender(<MemoryRouter><HomeCatalogueContext.Provider value={{data:home(b),changed:()=>{}}}><ForYou/></HomeCatalogueContext.Provider></MemoryRouter>)
 await screen.findAllByText('B Local 0');assert.equal(screen.queryByText('A Local 10'),null)
})
test('test_recommendation_paging_uses_one_scoped_fifty_pool',async()=>{
 const signal=new AbortController().signal;const one=await libraryRecommendationPage(a,signal,0,10);const two=await libraryRecommendationPage(a,signal,10,10)
 assert.ok(one.has_more&&two.has_more)
 assert.equal(new Set([...one.results,...two.results].map(r=>r.library_book_id)).size,20)
 assert.ok(calls.filter(p=>p.startsWith('/recommendation-api/')).every(p=>p.endsWith('limit=50&offset=0')))
})
test('test_recommendation_cold_start_tenant_local_discovery',async()=>{
 const fallback=globalThis.fetch;globalThis.fetch=async(input,init)=>String(input).startsWith('/recommendation-api/')?Response.json({recommendations:[]}):fallback(input,init)
 const result=await libraryRecommendationPage(a,new AbortController().signal)
 assert.ok(result.results.every(r=>r.library_id===a))
})
test('test_recommendation_foreign_projection_rejected',async()=>{
 const fallback=globalThis.fetch;globalThis.fetch=async(input,init)=>String(input).includes('/catalogue/recommendations')?Response.json({source:source(a),results:rows(b)}):fallback(input,init)
 await assert.rejects(libraryRecommendationPage(a,new AbortController().signal),/Library recommendation context changed/)
})
test('test_recommendation_view_all_preserves_context',async()=>{
 renderRail();await screen.findByRole('link',{name:'VIEW ALL'})
 assert.equal(screen.getByRole('link',{name:'VIEW ALL'}).getAttribute('href'),`/libraries/${a}/catalogue?view=for-you`)
})
test('test_recommendation_hnsw_and_kg_independent_projection',async()=>{
 await libraryRecommendationPage(a,new AbortController().signal)
 assert.equal(calls.some(p=>p.includes('/intelligence')||p.startsWith('/search-api')),false)
})
test('test_global_cold_start_view_all_preserves_popular_provider',async()=>{
 const fallback=globalThis.fetch
 globalThis.fetch=async(input,init)=>{
   const path=String(input)
   if(path.startsWith('/recommendation-api/'))return Response.json({recommendations:[]})
   if(path.includes('/books/popular'))return Response.json({results:[{book_id:1,work_id:'OL1W',title:'Popular cold start',authors:'QA',subjects:'Networks',average_rating:1}]})
   return fallback(input,init)
 }
 render(<MemoryRouter initialEntries={['/']}><ForYou/></MemoryRouter>)
 await screen.findByText('Popular books')
 assert.equal(screen.getByRole('link',{name:'VIEW ALL'}).getAttribute('href'),'/catalog?sort=popular')
})
