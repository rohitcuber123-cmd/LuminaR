import assert from 'node:assert/strict'
import {test,afterEach} from 'node:test'
import {registerHooks} from 'node:module'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5174'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,FormData:dom.window.FormData,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {GlobalCatalogue}=await import('../src/components/GlobalCatalogue')
const {SearchIntelligence}=await import('../src/components/SearchIntelligence')
const {useAuthStore}=await import('../src/store/useAuthStore')
const {searchContext,rememberSearch,clearSearchContexts,setPersonalizedSearch,personalizedSearch}=await import('../src/lib/searchContext')
afterEach(()=>{cleanup();localStorage.clear();sessionStorage.clear()})

function login(id=1){
 const user={user_id:id,email:`qa${id}@example.com`,role:'GENERAL_USER' as const}
 localStorage.setItem('luminar_user',JSON.stringify(user));localStorage.setItem('luminar_token','qa-token')
 useAuthStore.setState({token:'qa-token',isAuthenticated:true,user})
}

test('sessions and opt-in preference remain distinct for accounts libraries and workspaces',()=>{
 login();const global=searchContext(),a=searchContext({libraryId:'A'}),b=searchContext({libraryId:'B'}),staff=searchContext({libraryId:'A',staff:true})
 assert.equal(new Set([global.id,a.id,b.id,staff.id]).size,4)
 rememberSearch({libraryId:'A'},{active:true,expires_at:new Date(Date.now()+60000).toISOString()})
 assert.equal(searchContext({libraryId:'A'}).active,true);assert.equal(searchContext({libraryId:'B'}).active,false)
 assert.equal(personalizedSearch(),false);setPersonalizedSearch(true)
 login(2);assert.equal(personalizedSearch(),false);assert.notEqual(searchContext({libraryId:'A'}).id,a.id)
 sessionStorage.setItem('unrelated','preserved');clearSearchContexts()
 assert.equal(sessionStorage.getItem('unrelated'),'preserved')
})

test('session expiry discards identifiers without restoring old context',()=>{
 login();const old=searchContext()
 rememberSearch({},{active:true,expires_at:new Date(Date.now()-1).toISOString()})
 assert.notEqual(searchContext().id,old.id);assert.equal(searchContext().active,false)
})

test('Global UI refines with same server context, toggles independently and clears server state',async()=>{
 login();const calls:{path:string;body?:any;method?:string}[]=[];const original=globalThis.fetch
 globalThis.fetch=async(input,init={})=>{
  const path=String(input),body=init.body?JSON.parse(String(init.body)):undefined
  calls.push({path,body,method:init.method})
  if(path.endsWith('/facets'))return Response.json({results:[],capabilities:{rating:true,year:false,language:false,formats:['ONLINE'],availability:false}})
  if(path.includes('/categories'))return Response.json({categories:[]})
  if(path.includes('/search-context/'))return Response.json({cleared:true})
  if(path.endsWith('/search'))return Response.json({results:[],total_ranked_candidates:0,has_more:false,
   interpretation:{mode:'SMART',intent_label:'Discover topic',chips:[{key:'topic',label:'Topic: machine learning'},...(body.query==='online only'?[{key:'format',label:'Format: Online'}]:[])],corrections:[],session:{active:true,refined:body.query==='online only',version:1,expires_at:new Date(Date.now()+60000).toISOString()}}})
  return Response.json({books:[]})
 }
 try {
  render(<MemoryRouter initialEntries={['/search?q=machine+learning']}><GlobalCatalogue searchPage/></MemoryRouter>)
  await screen.findByRole('button',{name:'Clear search context'})
  const first=calls.find(c=>c.path.endsWith('/search'))!.body
  assert.equal(first.personalized,false);assert.ok(first.session_id);assert.equal(first.save_history,false)
  fireEvent.change(screen.getByRole('combobox',{name:'Search by title, author or subject'}),{target:{value:'online only'}})
  fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}))
  await screen.findByText('Refined from previous search')
  assert.equal(calls.filter(c=>c.path.endsWith('/search')).at(-1)!.body.session_id,first.session_id)
  assert.ok(screen.getByRole('button',{name:'Remove Topic: machine learning'}))
  fireEvent.click(screen.getByRole('checkbox',{name:'Personalized results'}))
  await waitFor(()=>assert.equal(calls.filter(c=>c.path.endsWith('/search')).at(-1)!.body.personalized,true))
  fireEvent.click(await screen.findByRole('button',{name:'Clear search context'}))
  await screen.findByText('Search the catalogue')
  assert.ok(calls.some(c=>c.method==='DELETE'&&c.path.includes(first.session_id)))
  assert.equal(searchContext().active,false)
 } finally {globalThis.fetch=original}
})

test('session UI is compact and preference removal is explicit',()=>{
 let clear=false,preference=false,omitted=''
 render(<main><SearchIntelligence params={new URLSearchParams()} facets={null} update={(k,v)=>{if(k==='omit')omitted=v}}
  context={{personalized:false,toggle:v=>{preference=v},clear:()=>{clear=true}}}
  interpretation={{mode:'SMART',chips:[],corrections:[],preference:'Introductory / beginner (preference)',session:{active:true,refined:true,version:1,expires_at:'future'}}}/></main>)
 fireEvent.click(screen.getByRole('checkbox',{name:'Personalized results'}));assert.equal(preference,true)
 fireEvent.click(screen.getByRole('button',{name:'Clear search context'}));assert.equal(clear,true)
 fireEvent.click(screen.getByRole('button',{name:/Remove Introductory/}));assert.equal(omitted,'preference')
})

test('session controls pass structural accessibility checks',async()=>{
 const view=render(<main><SearchIntelligence params={new URLSearchParams()} facets={null} update={()=>{}}
  context={{personalized:false,toggle:()=>{},clear:()=>{}}}
  interpretation={{mode:'SMART',chips:[{key:'format',label:'Format: Online'}],corrections:[],session:{active:true,refined:true,version:1,expires_at:'future'}}}/></main>)
 const axe=await import('axe-core')
 const report=await axe.default.run(view.container,{rules:{'color-contrast':{enabled:false}}})
 assert.deepEqual(report.violations.map(v=>v.id),[])
})

test('typed rejected interpretations use an accessible edit notice without a clarification dialog',async()=>{
 const view=render(<main><SearchIntelligence params={new URLSearchParams()} facets={null} update={()=>{}}
  context={{personalized:false,toggle:()=>{},clear:()=>{}}}
  interpretation={{mode:'SMART',chips:[],corrections:[],session:{active:true,refined:true,version:2,expires_at:'future'},decision:{decision_type:'CONTRADICTORY',safe_public_message:'These search filters conflict.',parser_version:'v2c-a'}}}/></main>)
 assert.match(screen.getByRole('status',{name:'Search interpretation decision'}).textContent || '',/These search filters conflict.*Edit your query/)
 assert.equal(screen.queryByRole('dialog'),null)
 assert.equal(screen.queryByText('Refined from previous search'),null)
 const axe=await import('axe-core')
 assert.deepEqual((await axe.default.run(view.container,{rules:{'color-contrast':{enabled:false}}})).violations.map(v=>v.id),[])
})
