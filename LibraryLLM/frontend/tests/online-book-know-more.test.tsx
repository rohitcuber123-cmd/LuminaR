import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor,act}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {LLMPage}=await import('../src/pages/LLMPage')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:store}=await import('../src/store/useInstitutionStore')
const {libraryKnowMorePath}=await import('../src/lib/libraryBookCapabilities')
const lib='11111111-1111-4111-8111-111111111111',book='22222222-2222-4222-8222-222222222222',assetId='33333333-3333-4333-8333-333333333333'
let original:typeof fetch,calls:{path:string;body?:string}[],status:number,asset:Record<string,unknown>
beforeEach(()=>{
 localStorage.clear();localStorage.setItem('luminar_token','online-session')
 auth.setState({token:'online-session',isAuthenticated:true,user:{user_id:1,name:'Reader',email:'reader@example.com',role:'GENERAL_USER'}})
 store.setState({session:'online-session',loading:false,libraries:[{library_id:lib,name:'Library',slug:'library',description:null,library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',membership:{membership_id:book,library_id:lib,user_id:1,role:'GENERAL_USER',status:'ACTIVE',is_owner:false,joined_at:'2026-10-14'}}]})
 asset={library_id:lib,asset_id:assetId,library_book_id:book,title:'Online Networking Book',original_filename:'networking.txt',status:'READY',visibility:'MEMBERS'}
 status=200;calls=[];original=globalThis.fetch
 globalThis.fetch=async(input,init={})=>{
  const path=String(input);calls.push({path,body:init.body as string|undefined})
  assert.equal(new Headers(init.headers).get('Authorization'),'Bearer online-session')
  if(status!==200)return Response.json({detail:'Resource unavailable'},{status})
  if(path.endsWith('/rag'))return Response.json({library_id:lib,asset_id:assetId,answer:'TCP retransmits lost packets.',verdict:'SUPPORTED',sources:[{filename:'networking.txt',page:2}]})
  if(path.endsWith('/artifacts'))return Response.json({artifacts:[]})
  if(path.endsWith('/context'))return Response.json({})
  return Response.json(asset)
 }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
function mount(path=libraryKnowMorePath(lib,book,assetId)){render(<MemoryRouter initialEntries={[path]}><LLMPage/></MemoryRouter>)}
test('online book opens in Know More without borrowed-book or private-document lookup',async()=>{
 mount();await screen.findByRole('heading',{name:'Online Networking Book'})
 assert.ok(screen.getByRole('button',{name:'Knowledge Tools'}))
 assert.ok(calls.length);assert.ok(calls.every(call=>call.path.includes(`/libraries/${lib}/assets/${assetId}`)))
 fireEvent.change(screen.getByLabelText('Question'),{target:{value:'How does TCP handle lost packets?'}})
 fireEvent.click(screen.getByRole('button',{name:'Ask',exact:true}))
 await screen.findByText('TCP retransmits lost packets.')
 const qa=calls.find(call=>call.path.endsWith('/rag'))!
 assert.ok(qa);assert.deepEqual(JSON.parse(qa.body!),{query:'How does TCP handle lost packets?',depth:'normal'})
})
test('online book Knowledge Tools use the library asset endpoint',async()=>{
 mount();await screen.findByRole('heading',{name:'Online Networking Book'})
 fireEvent.click(screen.getByRole('button',{name:'Knowledge Tools'}))
 await screen.findByText('Knowledge Tools · Entire Document')
 await waitFor(()=>assert.ok(calls.some(call=>call.path===`/rag-api/libraries/${lib}/assets/${assetId}/artifacts`)))
 assert.equal(calls.some(call=>call.path.includes('/rag/documents/')),false)
})
for(const kind of ['wrong book','processing','staff only','denied'])test(`online Know More blocks ${kind} sources before tools or QA`,async()=>{
 if(kind==='wrong book')asset.library_book_id=assetId
 if(kind==='processing')asset.status='PROCESSING'
 if(kind==='staff only')asset.visibility='STAFF_ONLY'
 if(kind==='denied')status=403
 mount();await screen.findByRole('alert')
 assert.equal(screen.queryByRole('button',{name:'Knowledge Tools'}),null)
 assert.equal(screen.queryByLabelText('Question'),null)
 assert.ok(calls.every(call=>!call.path.includes('/rag-api/')))
})
test('revoked source access clears its answer and tools',async()=>{
 mount();await screen.findByRole('heading',{name:'Online Networking Book'})
 fireEvent.change(screen.getByLabelText('Question'),{target:{value:'What is TCP?'}})
 fireEvent.click(screen.getByRole('button',{name:'Ask',exact:true}))
 await screen.findByText('TCP retransmits lost packets.')
 status=403
 act(()=>window.dispatchEvent(new Event('focus')))
 await screen.findByRole('alert')
 assert.equal(screen.queryByText('TCP retransmits lost packets.'),null)
 assert.equal(screen.queryByRole('button',{name:'Knowledge Tools'}),null)
})
