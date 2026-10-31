import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import { readFileSync } from 'node:fs'
import React from 'react'
import { JSDOM } from 'jsdom'
registerHooks({load(url,ctx,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,ctx)}})
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,waitFor,cleanup,act}=await import('@testing-library/react')
const {MemoryRouter,Routes,Route,useNavigate}=await import('react-router-dom')
const {LibraryIntelligencePage}=await import('../src/pages/LibraryIntelligence')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222'
const original=globalThis.fetch
let value:any,calls:{path:string,method:string}[],delayA=false,resolveA:(v:Response)=>void
function target(kind:string,state='NOT_BUILT'){return {target:kind,status:state,active_status:state,active_generation_id:state==='READY'||state==='STALE'?'generation-id':null,source_generation_id:'dataset-id',generation_sequence:4,record_count:150,built_at:'2026-10-13T12:00:00Z',last_build_duration_seconds:2,node_count:1093,edge_count:1111,artifact_verified:true,current_job:null,latest_job:null,can_retry:true,model:'all-MiniLM-L6-v2',dimension:384,parameters:{M:16,efConstruction:80,efSearch:64}}}
function job(state='RUNNING'){return {job_id:'job',library_id:a,target:'SEARCH_INDEX',state,stage:'EMBEDDING',progress_current:83,progress_total:150}}
function library(id:string,role='ADMIN'){return {library_id:id,name:id===a?'TEST':'Other library',membership:{role,status:'ACTIVE'}}}
beforeEach(()=>{cleanup();delayA=false;calls=[];localStorage.clear();localStorage.setItem('luminar_token','qa');auth.setState({token:'qa',isAuthenticated:true,user:{email:'qa@example.com'} as any});institutions.setState({libraries:[library(a),library(b)] as any});value={library_id:a,can_build:true,eligible_book_count:150,dataset:{generation_id:'dataset-id',sequence:1},search:target('SEARCH_INDEX'),kg:target('KNOWLEDGE_GRAPH')};globalThis.fetch=async(input,init)=>{const path=String(input),method=init?.method||'GET';calls.push({path,method});if(delayA&&path.includes(a)&&method==='GET')return new Promise(r=>{resolveA=r});if(method==='POST')return Response.json({...job('QUEUED'),target:JSON.parse(String(init?.body)).target});return Response.json({...value,library_id:path.includes(b)?b:a})}})
afterEach(()=>{cleanup();globalThis.fetch=original})
function page(){return render(<MemoryRouter initialEntries={[`/staff/libraries/${a}/intelligence`]}><Routes><Route path="/staff/libraries/:libraryId/intelligence" element={<LibraryIntelligencePage/>}/></Routes></MemoryRouter>)}
async function ready(){page();await screen.findByRole('heading',{name:'Semantic Search Index'})}

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
