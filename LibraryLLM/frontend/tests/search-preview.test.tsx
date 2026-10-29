import assert from 'node:assert/strict'
import {test,afterEach} from 'node:test'
import {registerHooks} from 'node:module'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5174/search?search_preview=1'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,HTMLInputElement:dom.window.HTMLInputElement,HTMLTextAreaElement:dom.window.HTMLTextAreaElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor,act}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {SearchPreview}=await import('../src/components/SearchPreview')
const {useSearchPreviewGate}=await import('../src/lib/searchPreview')
const {useAuthStore}=await import('../src/store/useAuthStore')
const original=globalThis.fetch
afterEach(()=>{cleanup();globalThis.fetch=original;localStorage.clear();sessionStorage.clear()})
function login(){localStorage.setItem('luminar_token','preview-fixture');localStorage.setItem('luminar_user',JSON.stringify({user_id:2,email:'fixture@example.com',role:'GENERAL_USER'}));useAuthStore.setState({token:'preview-fixture',isAuthenticated:true})}
function response(query='books about biology',version=1,overrides:any={}){return {results:[],total:null,offset:0,limit:10,has_more:false,
  coverage:{kind:'RANKED_CANDIDATE_WINDOW',complete:false,notice:'Filters are enforced within a bounded search window.'},
  interpretation:{mode:'SMART',chips:[],corrections:[]},
  preview:{state_id:'server-state',accepted_plan_version:version,original_query:query,accepted_query:query,parser_version:'v11',source_digest:'source',ir_digest:'ir',expires_at:'future',mode:'SMART',operations:[],decision:'EXECUTABLE',message:'',...overrides}}}
function view(props:React.ComponentProps<typeof SearchPreview>={}){return render(<MemoryRouter><SearchPreview {...props}/></MemoryRouter>)}
function Gate({requested}:{requested:boolean}){const gate=useSearchPreviewGate(requested);return <p>{gate.pending?'pending':gate.enabled?'preview':'standard'}</p>}
async function submit(query='books about biology'){fireEvent.change(screen.getByRole('textbox',{name:'Search query'}),{target:{value:query}});fireEvent.click(screen.getByRole('button',{name:'Search'}))}

test('preview is opt-in and server denial retains standard search',async()=>{
 login();let calls=0;globalThis.fetch=async()=>{calls++;return Response.json({smart_preview:false})}
 const v=render(<Gate requested={false}/>);assert.ok(screen.getByText('standard'));assert.equal(calls,0)
 v.rerender(<Gate requested/>);await waitFor(()=>assert.equal(calls,1));await screen.findByText('standard')
})

test('500 Unicode characters are sent intact and excess is validated without truncation',async()=>{
 login();const sent:any[]=[];globalThis.fetch=async(_,options={})=>{const body=JSON.parse(String(options.body));sent.push(body);return Response.json(response(body.query))}
 view();const q='🪴'.repeat(500);await submit(q);await screen.findByText('Accepted query:')
 assert.equal(sent[0].query,q);assert.equal(Array.from(sent[0].query).length,500)
 fireEvent.change(screen.getByRole('textbox',{name:'Search query'}),{target:{value:q+'x'}})
 assert.match(screen.getByRole('alert').textContent||'',/501\/500/);assert.ok((screen.getByRole('button',{name:'Search'}) as HTMLButtonElement).disabled)
 assert.equal((screen.getByRole('textbox',{name:'Search query'}) as HTMLTextAreaElement).value,q+'x')
})

test('accepted source versions and issued completion IDs round-trip then restore focus',async()=>{
 login();const sent:any[]=[]
 globalThis.fetch=async(_,options={})=>{const body=JSON.parse(String(options.body));sent.push(body);return Response.json(sent.length===1?response(body.query,1,{decision:'INCOMPLETE',message:'Which author?',operations:[{operation_id:'issued-author',kind:'complete',field:'author',label:'Complete author',input_type:'text'}]}):response('books about biology; by "Ada Sage"',2))}
 view();await submit('books about biology; by [author]');await screen.findByText('Which author?')
 fireEvent.change(screen.getByRole('textbox',{name:'Complete author'}),{target:{value:'Ada Sage'}});fireEvent.click(screen.getByRole('button',{name:'Apply'}))
 await waitFor(()=>assert.equal(sent.length,2));await waitFor(()=>assert.equal((screen.getByRole('textbox',{name:'Search query'}) as HTMLTextAreaElement).value,'books about biology; by "Ada Sage"'))
 assert.equal(sent[1].state_id,'server-state');assert.equal(sent[1].version,1);assert.equal(sent[1].operation_id,'issued-author');assert.equal(sent[1].value,'Ada Sage')
 assert.equal(document.activeElement,screen.getByRole('textbox',{name:'Search query'}))
})

test('enforced filter chips and advisory preferences are distinct',async()=>{
 login();globalThis.fetch=async()=>Response.json({...response('biology',1,{advisory:'Prefer practical explanations'}),interpretation:{mode:'SMART',chips:[{key:'rating_min',label:'Rating: ≥ 4'},{key:'topic',label:'Topic: biology'}],corrections:[]}})
 view();await submit('biology');assert.ok(await screen.findByRole('group',{name:'Enforced filters'}));assert.ok(screen.getByText('Rating: ≥ 4'));assert.ok(screen.getByText('Preference: Prefer practical explanations'));assert.equal(screen.queryByText('Topic: biology'),null)
 assert.ok(screen.getByText(/bounded search window/))
})

test('unsupported requirements render a targeted explanation without filter claims',async()=>{
 login();globalThis.fetch=async()=>Response.json(response('books under 100 pages',1,{decision:'UNSUPPORTED',message:'This catalogue cannot filter page count.'}))
 view();await submit('books under 100 pages');assert.ok(await screen.findByText('This catalogue cannot filter page count.'));assert.equal(screen.queryByRole('group',{name:'Enforced filters'}),null)
})

test('Apply and Keep send server-issued operations without proposing a native plan',async()=>{
 login();let body:any;globalThis.fetch=async(_,options={})=>{body=JSON.parse(String(options.body));return Response.json(body.operation_id?response('about "Detectve Fiction"',2):response(body.query,1,{decision:'AMBIGUOUS',message:'Confirm category correction',operations:[{operation_id:'apply',kind:'correction_apply',label:'Apply correction'},{operation_id:'keep',kind:'correction_keep',label:'Keep my wording'}]}))}
 view();await submit('include subject "Detectve Fiction"');fireEvent.click(await screen.findByRole('button',{name:'Keep my wording'}))
 await waitFor(()=>assert.equal(body.operation_id,'keep'));assert.equal(body.plan,undefined);await waitFor(()=>assert.equal((screen.getByRole('textbox',{name:'Search query'}) as HTMLTextAreaElement).value,'about "Detectve Fiction"'))
})

test('mode switch clears stale state and Exact submission stays explicit',async()=>{
 login();const sent:any[]=[];globalThis.fetch=async(_,options={})=>{const b=JSON.parse(String(options.body));sent.push(b);return Response.json(response(b.query))}
 view();await submit('biology');await screen.findByText('Accepted query:')
 // Native custom select uses button/listbox semantics.
 const mode=screen.getByRole('combobox',{name:'Search mode'});fireEvent.click(mode);fireEvent.click(screen.getByRole('option',{name:'Exact'}))
 await submit('A Quiet River');await waitFor(()=>assert.equal(sent.length,2));assert.equal(sent[1].mode,'EXACT');assert.equal(sent[1].state_id,undefined)
})

test('library change cannot display a late private response',async()=>{
 login();let complete:((r:Response)=>void)|undefined
 globalThis.fetch=async()=>new Promise(resolve=>{complete=resolve})
 const v=view({libraryId:'library-a'});await submit('private orchid');await waitFor(()=>assert.ok(complete))
 v.rerender(<MemoryRouter><SearchPreview key="library-b" libraryId="library-b"/></MemoryRouter>)
 await act(async()=>complete!(Response.json(response('private orchid'))))
 assert.equal(screen.queryByText('Accepted query:'),null);assert.equal((screen.getByRole('textbox',{name:'Search query'}) as HTMLTextAreaElement).value,'')
})

test('foreign library serialization is rejected even if transport succeeds',async()=>{
 login();globalThis.fetch=async()=>Response.json({...response(),source:{library_id:'foreign',catalogue_source:'LIBRARY_LOCAL'},results:[]})
 view({libraryId:'library-a'});await submit();assert.ok(await screen.findByText(/library context changed/));assert.equal(screen.queryByText('Accepted query:'),null)
})

test('provider errors keep original input and allow an explicit retry',async()=>{
 login();globalThis.fetch=async()=>Response.json({detail:'Search is temporarily unavailable.'},{status:503})
 view();await submit('biology');assert.ok(await screen.findByText(/Search is temporarily unavailable/));assert.equal((screen.getByRole('textbox',{name:'Search query'}) as HTMLTextAreaElement).value,'biology')
 globalThis.fetch=async()=>Response.json(response('biology'));fireEvent.click(screen.getByRole('button',{name:'Retry'}));await screen.findByText('Accepted query:')
})

test('initial query submits once despite accepted-source URL restoration',async()=>{
 login();let calls=0;globalThis.fetch=async()=>{calls++;return Response.json(response('biology'))}
 view({initialQuery:'biology'});await screen.findByText('Accepted query:');await act(async()=>new Promise(r=>setTimeout(r,20)));assert.equal(calls,1)
})

test('StrictMode initial mount and repeated clicks do not duplicate requests',async()=>{
 login();let calls=0,complete:((r:Response)=>void)|undefined
 globalThis.fetch=async()=>{calls++;return new Promise(resolve=>{complete=resolve})}
 render(<React.StrictMode><MemoryRouter><SearchPreview initialQuery="biology"/></MemoryRouter></React.StrictMode>)
 await waitFor(()=>assert.equal(calls,1));fireEvent.click(screen.getByRole('button',{name:'Searching…'}));assert.equal(calls,1)
 await act(async()=>complete!(Response.json(response('biology'))));await screen.findByText('Accepted query:')
})
