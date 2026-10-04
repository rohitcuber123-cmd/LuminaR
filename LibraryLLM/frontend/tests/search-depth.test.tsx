import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost:5173'})
class Observer { observe() {} disconnect() {} unobserve() {} }
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,
 HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true,IntersectionObserver:Observer,ResizeObserver:Observer})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
localStorage.setItem('luminar_token','fixture-token')
localStorage.setItem('luminar_user',JSON.stringify({email:'fixture@example.com',role:'GENERAL_USER'}))
const {render,screen,fireEvent,cleanup,waitFor}=await import('@testing-library/react')
const {MemoryRouter,useNavigate}=await import('react-router-dom')
const {SearchPage}=await import('../src/pages/SearchPage.tsx')
const {ForYou}=await import('../src/components/ForYou.tsx')
const {changeSearchContext,searchPaging}=await import('../src/lib/searchPaging.ts')
const {useAuthStore}=await import('../src/store/useAuthStore.ts')
let calls:Array<{url:string;body:any}>=[], more=true
const original=globalThis.fetch
function row(i:number){return {work_id:`OL${i}W`,title:`Depth book ${i}`,authors:`Author ${i}`,subjects:'Subject',total_copies:1,available_copies:1,physical_copies:1,available_physical_copies:1,library_available:true}}
beforeEach(()=>{
 calls=[];more=true
 useAuthStore.setState({token:'fixture-token'})
 globalThis.fetch=async (url,options)=>{
  const text=String(url),body=options?.body?JSON.parse(String(options.body)):null
  calls.push({url:text,body})
  let result:any={books:[]}
  if(text.includes('/search-api/search')) result={query:body.query,results:Array.from({length:10},(_,i)=>row(body.offset+i)),has_more:more,next_offset:body.offset+10,offset:body.offset,limit:10}
  if(text.includes('/recommendations?')) {const params=new URL(text,'http://localhost').searchParams;const offset=Number(params.get('offset'));result={recommendations:Array.from({length:10},(_,i)=>row(offset+i)),has_more:more,offset,limit:10,recommendation_mode:'PERSONALIZED_EXISTING_FORMULA',seed_work_ids:[]}}
  return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}})
 }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
function ChangeQuery(){const navigate=useNavigate();return <button onClick={()=>navigate('/search?q=new+query')}>Change query</button>}
async function search(initial='/search?q=manage+money&available=true'){
 render(<MemoryRouter initialEntries={[initial]}><ChangeQuery/><SearchPage/></MemoryRouter>)
 await screen.findAllByText('Depth book 0')
}
test('Search Next Results sends next offset and preserves query and filters; Previous restores first slice',async()=>{
 await search()
 assert.ok((screen.getByRole('button',{name:'Previous'}) as HTMLButtonElement).disabled)
 fireEvent.click(screen.getByRole('button',{name:'Next Results'}))
 await screen.findAllByText('Depth book 10')
 const request=calls.filter(call=>call.url.includes('/search-api/search')).at(-1)!.body
 assert.equal(request.offset,10);assert.equal(request.query,'manage money');assert.equal(request.available_at_library,true);assert.equal(request.limit,10)
 assert.equal(screen.queryAllByText('Depth book 0').length,0)
 fireEvent.click(screen.getByRole('button',{name:'Previous'}));await screen.findAllByText('Depth book 0')
})
test('Query and availability changes reset offset to zero',async()=>{
 await search('/search?q=manage+money')
 fireEvent.click(screen.getByRole('button',{name:'Next Results'}));await screen.findAllByText('Depth book 10')
 fireEvent.click(screen.getByRole('checkbox',{name:'Available now'}));await screen.findAllByText('Depth book 0')
 let request=calls.filter(call=>call.url.includes('/search-api/search')).at(-1)!.body
 assert.equal(request.offset,0);assert.equal(request.available_at_library,true)
 fireEvent.click(screen.getByRole('button',{name:'Next Results'}));await screen.findAllByText('Depth book 10')
 fireEvent.click(screen.getByRole('button',{name:'Change query'}));await screen.findAllByText('Depth book 0')
 request=calls.filter(call=>call.url.includes('/search-api/search')).at(-1)!.body
 assert.equal(request.offset,0);assert.equal(request.query,'new query')
})
test('Search exhausted pool disables Next Results',async()=>{
 more=false;await search();assert.ok((screen.getByRole('button',{name:'Next Results'}) as HTMLButtonElement).disabled)
})
test('URL paging preserves state and context change clears old offset',()=>{
 const params=new URLSearchParams('q=old&offset=20&available=true&library=LIB001')
 assert.equal(searchPaging(params).offset,20)
 const next=changeSearchContext(params,{q:'new'});assert.equal(searchPaging(next).offset,0);assert.equal(next.get('available'),'true')
 assert.equal(searchPaging(new URLSearchParams('offset=5000000')).offset,0)
})
test('For You advances the existing recommendation mode through disjoint slices',async()=>{
 render(<MemoryRouter><ForYou/></MemoryRouter>);await screen.findAllByText('Depth book 0')
 fireEvent.click(screen.getByRole('button',{name:'Next Recommendations'}));await screen.findAllByText('Depth book 10')
 assert.ok(calls.some(call=>call.url.endsWith('limit=10&offset=10')))
 assert.equal(screen.queryAllByText('Depth book 0').length,0)
 assert.ok(screen.getByText('Recommendations 11–20'))
 fireEvent.click(screen.getByRole('button',{name:'Previous'}));await screen.findAllByText('Depth book 0')
})
test('For You has_more false disables continuation',async()=>{
 more=false;render(<MemoryRouter><ForYou/></MemoryRouter>);await screen.findAllByText('Depth book 0')
 assert.ok((screen.getByRole('button',{name:'Next Recommendations'}) as HTMLButtonElement).disabled)
})


test('For You failed continuation clears old cards and offers Previous',async()=>{
 render(<MemoryRouter><ForYou/></MemoryRouter>);await screen.findAllByText('Depth book 0')
 const successfulFetch=globalThis.fetch
 globalThis.fetch=async (url,options)=>String(url).includes('offset=10') ? new Response(JSON.stringify({detail:'Temporarily unavailable'}),{status:503,headers:{'Content-Type':'application/json'}}) : successfulFetch(url,options)
 fireEvent.click(screen.getByRole('button',{name:'Next Recommendations'}))
 await screen.findByText('Recommendations could not be loaded. Try Previous.')
 assert.equal(screen.queryAllByText('Depth book 0').length,0)
 assert.ok((screen.getByRole('button',{name:'Next Recommendations'}) as HTMLButtonElement).disabled)
 fireEvent.click(screen.getByRole('button',{name:'Previous'}));await screen.findAllByText('Depth book 0')
})
