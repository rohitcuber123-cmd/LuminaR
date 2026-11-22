import assert from 'node:assert/strict'
import {test,beforeEach,afterEach} from 'node:test'
import {JSDOM} from 'jsdom'
import React from 'react'
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {assistantChat}=await import('../src/lib/assistant')
const {useAssistantStore:store}=await import('../src/store/useAssistantStore')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const {render,screen,cleanup,act}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {BookPersonalActions}=await import('../src/components/BookPersonalActions')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333'
const original=globalThis.fetch
let bodies:any[]=[]
const response={conversation_id:'scope-test',intent:'SEARCH_BOOKS',message:'Scoped fixture',books:[],comparison:null,recommendation_mode:null,seed_work_ids:[],availability:[],actions:[],clarification:null,pending_action:null,account:null,reading_list:null,rag:null,errors:[],has_more:false,result_offset:0,explanation_available:false}
beforeEach(()=>{window.history.replaceState({},'','/catalog');localStorage.clear();sessionStorage.clear();localStorage.setItem('luminar_token','scope-session');localStorage.setItem('luminar_user',JSON.stringify({email:'scope@example.com'}));auth.setState({token:'scope-session',isAuthenticated:true,user:{user_id:1,email:'scope@example.com',role:'GENERAL_USER'} as any});institutions.setState({session:'scope-session',loading:false,activeId:a,libraries:[a,b].map(library_id=>({library_id,name:'Scope Library',membership:{library_id,role:'GENERAL_USER',status:'ACTIVE'}})) as any});store.setState({owner:'scope@example.com',sessionToken:'scope-session',libraryScope:'GLOBAL',pagePath:'',pageContext:{},messages:[],recent:[],selected:[],conversationId:null,busy:false});bodies=[];globalThis.fetch=async(_url,options)=>{bodies.push(JSON.parse(String(options?.body)));return Response.json(response)}})
afterEach(()=>{cleanup();globalThis.fetch=original})

test('digital result renders canonical PDF link without physical stock badge',async()=>{
  const {AssistantTurn}=await import('../src/components/assistant/AssistantTurn')
  const data={...response,intent:'CHECK_AVAILABILITY',message:'Authorized digital resource ready.',
    books:[{work_id:id,library_id:a,library_book_id:id,title:'Local PDF',available_copies:99,total_copies:100}],
    digital_availability:[{work_id:id,library_id:a,status:'AUTHORIZED',catalogue_present:true,resource_link_present:true,
      asset_present:true,access_authorized:true,full_text_accessible:true,
      resources:[{kind:'LIBRARY_DOCUMENT',asset_type:'PDF',asset_id:b,href:`/libraries/${a}/resources/${b}`}]}]}
  render(<MemoryRouter><AssistantTurn response={data as any} busy={false} pendingActive={false} now={0} onAction={()=>{}} onChoice={()=>{}}/></MemoryRouter>)
  assert.equal(screen.getByRole('link',{name:'Open PDF'}).getAttribute('href'),`/libraries/${a}/resources/${b}`)
  assert.equal(screen.queryByText(/99 copies/),null)
})

test('unknown digital access does not invent a download or physical availability',async()=>{
  const {AssistantTurn}=await import('../src/components/assistant/AssistantTurn')
  const data={...response,intent:'CHECK_AVAILABILITY',message:'Digital access cannot be verified.',
    books:[{work_id:id,title:'Physical only',available_copies:99}],
    digital_availability:[{work_id:id,library_id:a,status:'UNKNOWN',catalogue_present:true,resource_link_present:false,
      asset_present:null,access_authorized:null,full_text_accessible:null,resources:[]}]}
  render(<MemoryRouter><AssistantTurn response={data as any} busy={false} pendingActive={false} now={0} onAction={()=>{}} onChoice={()=>{}}/></MemoryRouter>)
  assert.equal(screen.queryByRole('link',{name:/Open PDF/}),null)
  assert.ok(screen.getByText(/Digital access not verified/))
  assert.equal(screen.queryByText(/99 copies/),null)
})
test('transport keeps legitimate circulation and effective scope fields',async()=>{await assistantChat({message:'Request this book',library_id:a,lending_context:{library_id:a,library_book_id:id,loan_id:id,reservation_id:id},selected_work_ids:[],recent_work_ids:[],page_context:{}});assert.equal(bodies[0].library_id,a);assert.deepEqual(bodies[0].lending_context,{library_id:a,library_book_id:id,loan_id:id,reservation_id:id})})
test('transport explicitly discards unrelated client fields',async()=>{await assistantChat({message:'Hello',selected_work_ids:[],recent_work_ids:[],page_context:{},user_id:999,role:'ADMIN'} as any);assert.equal(bodies[0].user_id,undefined);assert.equal(bodies[0].role,undefined)})
for(const [from,to] of [['GLOBAL',a],[a,b],[b,'GLOBAL'],[a,'GLOBAL']])test(`scope switch ${from} to ${to} clears references`,()=>{store.setState({libraryScope:from,conversationId:'foreign',selected:[{work_id:id,title:'Private'}],recent:[id],messages:[{id:1,kind:'SYSTEM_NOTICE',text:'Private history'}]});store.getState().setPageContext(to==='GLOBAL'?'/catalog':`/libraries/${to}/catalogue`,{});assert.equal(store.getState().conversationId,null);assert.deepEqual(store.getState().selected,[]);assert.deepEqual(store.getState().recent,[]);assert.deepEqual(store.getState().messages,[]);assert.equal(JSON.parse(sessionStorage.getItem('luminar_assistant_session')!).libraryScope,to)})
test('send follows canonical route scope',async()=>{window.history.replaceState({},'',`/libraries/${a}/catalogue`);await store.getState().send('Find Python books',{});assert.equal(bodies[0].library_id,a);assert.equal(bodies[0].lending_context.library_id,a)})
test('late response cannot cross a library transition',async()=>{window.history.replaceState({},'',`/libraries/${a}/catalogue`);let finish!:(v:Response)=>void;globalThis.fetch=async()=>new Promise(resolve=>{finish=resolve});const pending=store.getState().send('Find books',{});store.getState().setPageContext(`/libraries/${b}/catalogue`,{});finish(Response.json({...response,message:'SECRET A'}));await pending;assert.equal(store.getState().libraryScope,b);assert.deepEqual(store.getState().messages,[]);assert.equal(store.getState().conversationId,null)})
test('scoped authorization failure clears prior protected history',async()=>{window.history.replaceState({},'',`/libraries/${a}/catalogue`);store.getState().setPageContext(`/libraries/${a}/catalogue`,{});store.setState({conversationId:'old',messages:[{id:1,kind:'SYSTEM_NOTICE',text:'SECRET A'}]});globalThis.fetch=async()=>Response.json({detail:'Unavailable'},{status:404});await store.getState().send('Follow up',{});assert.equal(store.getState().conversationId,null);assert.ok(!JSON.stringify(store.getState().messages).includes('SECRET A'))})
const local={display_id:id,library_book_id:id,library_id:a,global_work_id:null,source:'LIBRARY',owned_by_current_library:true,title:'Local-only fixture',authors:['Ada']} as any
test('local-only book exposes selection in its authorized library',()=>{render(<MemoryRouter initialEntries={[`/libraries/${a}/catalogue`]}><BookPersonalActions book={local}/></MemoryRouter>);assert.ok(screen.getByRole('button',{name:'Select Local-only fixture'}))})
test('local-only book cannot be selected into a Global conversation',()=>{render(<MemoryRouter initialEntries={['/catalog']}><BookPersonalActions book={local} detailed/></MemoryRouter>);assert.equal(screen.queryByRole('button',{name:'Select Local-only fixture'}),null)})

test('router path wins over stale page metadata during a transition',async()=>{store.getState().setPageContext(`/libraries/${a}/catalogue`,{});store.setState({conversationId:'A-history',recent:[id],selected:[{work_id:id,title:'Private A'}]});await store.getState().send('Find books',{work_id:id},{page_path:`/libraries/${b}/catalogue`});assert.equal(bodies[0].library_id,b);assert.equal(bodies[0].conversation_id,null);assert.deepEqual(bodies[0].recent_work_ids,[]);assert.deepEqual(bodies[0].page_context,{});assert.equal(bodies[0].page_path,undefined)})
test('comparison does not expose transport identifiers as catalogue facts',async()=>{const {ComparisonView}=await import('../src/components/assistant/AssistantTurn');render(<ComparisonView comparison={{books:[{work_id:id,title:'Private book',authors:['Ada'],library_id:a,library_book_id:id}],requested_fields:[],missing_fields:[]} as any} availability={[]} busy={false}/>);assert.equal(screen.queryByText(a),null);assert.equal(screen.queryByText(id),null)})

test('unowned Global discovery card cannot seed the private assistant',()=>{render(<MemoryRouter initialEntries={[`/libraries/${a}/catalogue`]}><BookPersonalActions book={{...local,source:'GLOBAL',owned_by_current_library:false,library_book_id:null,global_work_id:'OL1W'}}/></MemoryRouter>);assert.equal(screen.queryByRole('button',{name:'Select Local-only fixture'}),null)})

test('role change clears private transcript and pending references',async()=>{const {AIChatWidget}=await import('../src/components/AIChatWidget');store.setState({libraryScope:a,open:true,messages:[{id:1,kind:'SYSTEM_NOTICE',text:'Private prior role'}],conversationId:'prior-role',recent:[id]});render(<MemoryRouter initialEntries={[`/libraries/${a}/catalogue`]}><AIChatWidget/></MemoryRouter>);act(()=>institutions.setState({libraries:[{library_id:a,name:'Scope Library',membership:{library_id:a,role:'LIBRARIAN',status:'ACTIVE'}}] as any}));assert.equal(store.getState().conversationId,null);assert.deepEqual(store.getState().messages,[]);assert.deepEqual(store.getState().recent,[])})

test('mismatched cached transcript cannot render beneath another library indicator',async()=>{const {AIChatWidget}=await import('../src/components/AIChatWidget');store.setState({libraryScope:a,open:true,messages:[]});render(<MemoryRouter initialEntries={[`/libraries/${a}/catalogue`]}><AIChatWidget/></MemoryRouter>);act(()=>store.setState({libraryScope:b,messages:[{id:1,kind:'SYSTEM_NOTICE',text:'FOREIGN PRIVATE B'}]}));assert.equal(screen.queryByText('FOREIGN PRIVATE B'),null)})
