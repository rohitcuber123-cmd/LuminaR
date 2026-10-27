import assert from 'node:assert/strict'
import { readFileSync,writeFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { test,beforeEach,afterEach,after } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { DisplayBook } from '../src/lib/libraryCatalogue'
registerHooks({load(url,context,next){return url.endsWith('.css') ? {format:'module',source:'',shortCircuit:true} : next(url,context)}})
const dom=new JSDOM('<!doctype html><html lang="en"><head><title>Convergence</title></head><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,FormData:dom.window.FormData,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
class Observer {observe(){}disconnect(){}unobserve(){}}
Object.assign(globalThis,{IntersectionObserver:Observer,ResizeObserver:Observer})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,waitFor,cleanup,act}=await import('@testing-library/react')
const {MemoryRouter,useLocation,Link}=await import('react-router-dom')
const {BookCard}=await import('../src/components/BookCard')
const {BookDetailView}=await import('../src/components/BookDetailView')
const {GlobalCatalogue}=await import('../src/components/GlobalCatalogue')
const {ReadingListPage}=await import('../src/pages/ReadingListPage')
const {Header}=await import('../src/components/Header')
const {AccountProfilePage}=await import('../src/pages/AccountPages')
const {AIChatWidget}=await import('../src/components/AIChatWidget')
const {ToastContainer}=await import('../src/components/Toast')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const {useLibraryStore:saved}=await import('../src/store/useLibraryStore')
const {useAssistantStore:assistant}=await import('../src/store/useAssistantStore')
const {globalDisplayBook}=await import('../src/lib/libraryCatalogue')
const {productLibraryId,withPatronContext}=await import('../src/lib/productContext')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',bid='33333333-3333-4333-8333-333333333333'
const record={work_id:'OL1W',book_id:17,title:'Shared Atlas',authors:'Ada',subjects:'Networking',description:'A real description',total_copies:999,available_copies:999,shelf_location:'GLOBAL FAKE'}
const global=()=>globalDisplayBook(record,'')
const local=(linked=true):DisplayBook=>({...global(),library_id:a,library_book_id:bid,display_id:bid,global_work_id:linked?'OL1W':null,source:'LIBRARY',owned_by_current_library:true,cover_seed:17,requestable_count:1,circulation_status:'CIRCULATING',shelf_location:'A / 01',accession_number:'A-01',actions:{request:true,reserve:false,cancel_request:false,cancel_reservation:false}})
const membership=(id:string)=>({library_id:id,name:id===a?'TEST':'Other library',membership:{library_id:id,membership_id:id,user_id:1,role:'GENERAL_USER',status:'ACTIVE'}})
const original=globalThis.fetch
let calls:{path:string;body:any;method:string}[]=[],failSave=false,items:any[]=[],deferred:((value:Response)=>void)|null=null
const matrix=JSON.parse(readFileSync(new URL('../../reports/full_feature_parity_matrix.json',import.meta.url),'utf8'))
const planned:{name:string;features:string[];status:string}[]=[]
function parity(name:string,features:string[],run:()=>void|Promise<void>){
  for(const id of features)assert.ok(matrix.features.some((f:any)=>f.id===id),'Unknown parity feature '+id)
  const row={name,features,status:'PLANNED'};planned.push(row)
  test(name,async()=>{try{await run();row.status='PASS'}catch(e){row.status='FAIL';throw e}})
}
after(()=>writeFileSync(new URL('../../reports/full_product_generated_test_plan.json',import.meta.url),JSON.stringify(planned,null,2)))
beforeEach(()=>{
  localStorage.clear();sessionStorage.clear();localStorage.setItem('luminar_token','convergence');localStorage.setItem('luminar_user',JSON.stringify({email:'test@example.com',role:'ADMIN'}))
  auth.setState({token:'convergence',user:{user_id:1,email:'test@example.com',name:'Account',role:'ADMIN'},isAuthenticated:true})
  saved.getState().clearUserData();saved.setState({userDataLoaded:true})
  institutions.setState({session:'convergence',libraries:[membership(a),membership(b)] as any,activeId:b,patronLibraryId:b,workspace:'PATRON',loading:false,error:null})
  assistant.getState().syncSession('test@example.com','convergence');assistant.setState({selected:[],messages:[],busy:false,pagePath:'',pageContext:{}})
  calls=[];failSave=false;items=[];deferred=null
  globalThis.fetch=async(url,options)=>{
    const path=String(url),body=options?.body?JSON.parse(String(options.body)):null,method=options?.method || 'GET';calls.push({path,body,method})
    if(path==='/api/reading-list/' && method==='POST'){
      if(deferred!==null)return await new Promise<Response>(resolve=>{deferred=resolve})
      if(failSave)return new Response(JSON.stringify({detail:'Save unavailable'}),{status:503,headers:{'Content-Type':'application/json'}})
      return Response.json({target_key:body.work_id})
    }
    if(path==='/api/reading-list/my')return Response.json({items,count:items.length})
    if(path.startsWith('/api/books/categories'))return Response.json({categories:[{name:'Networking',count:23}],count:1})
    if(path.startsWith('/api/books/?')) {const offset=Number(new URL(path,'http://localhost').searchParams.get('offset') || 0);return Response.json({count:null,has_more:offset===0,results:[{...record,work_id:offset?'OL2W':'OL1W',title:offset?'Second slice':'Shared Atlas'}]})}
    if(path.startsWith('/recommendation-api/recommendations'))return Response.json({recommendations:[record],total_ranked_candidates:1,has_more:false})
    if(path==='/rag-api/assistant/chat')return Response.json({conversation_id:'test',intent:'GENERAL_LIBRARY_HELP',message:'Verified help',books:[],availability:[],actions:[],errors:[],reading_list:null})
    return Response.json({items:[],count:0,issues:[],reservations:[],results:[],books:[]})
  }
})
afterEach(async()=>{await act(async()=>{await Promise.resolve()});cleanup();globalThis.fetch=original})
function Position(){const p=useLocation();return <output data-testid="url">{p.pathname+p.search}</output>}
function mount(child:React.ReactNode,path='/'){return render(<MemoryRouter initialEntries={[path]}><Position/>{child}</MemoryRouter>)}
for(const context of ['GLOBAL','LIBRARY'] as const){
  parity(context+' save and AI selection share the global identity',['reading-list','saved-linked','ai','counter','cards'],async()=>{
    mount(<><BookCard book={context==='GLOBAL'?global():local()} /><AIChatWidget/></>,context==='GLOBAL'?'/catalog':`/libraries/${a}/catalogue`)
    fireEvent.click(screen.getByRole('button',{name:'Add to Reading List'}));await screen.findByRole('button',{name:'In Reading List ✓'})
    assert.deepEqual(saved.getState().readingList,['OL1W']);assert.equal(calls.find(c=>c.method==='POST')!.body.work_id,'OL1W')
    fireEvent.click(screen.getByRole('button',{name:'Select Shared Atlas'}));assert.deepEqual(assistant.getState().selected.map(b=>b.work_id),['OL1W'])
    assert.ok(screen.getByLabelText('1 selected books'));assert.equal(calls.some(c=>c.path.includes('/issues/') && c.method==='POST'),false)
  })
  parity(context+' detail has truthful facts and accessible personal actions',['detail','covers','accessibility','loading'],async()=>{
    const view=mount(<BookDetailView book={context==='GLOBAL'?global():local()} backPath={context==='GLOBAL'?'/catalog':`/libraries/${a}/catalogue`} />)
    assert.ok(screen.getByRole('heading',{level:1,name:'Shared Atlas'}));assert.ok(screen.getByText('A real description'))
    assert.equal(screen.queryByText('GLOBAL FAKE'),null);assert.equal(screen.queryByRole('button',{name:'BORROW'}),null)
    if(context==='LIBRARY')assert.ok(screen.getByText('A-01'))
    const axe=await import('axe-core');const result=await axe.default.run(view.container,{rules:{'color-contrast':{enabled:false},region:{enabled:false}}})
    assert.deepEqual(result.violations.map(v=>v.id),[])
  })
}
parity('local-only save is visible while AI limitation is explicit',['saved-local','ai-local','detail'],async()=>{
  mount(<BookDetailView book={local(false)} backPath={`/libraries/${a}/catalogue`} />)
  assert.equal(screen.queryByRole('button',{name:'Select Shared Atlas'}),null);assert.ok(screen.getByText(/AI selection and related discovery require/))
  fireEvent.click(screen.getByRole('button',{name:'Add to Reading List'}));await screen.findByRole('button',{name:'In Reading List ✓'})
  assert.deepEqual(saved.getState().readingList,[`local:${a}:${bid}`])
})
parity('failed save preserves state and reports the error',['saved-linked','errors'],async()=>{
  failSave=true;mount(<BookCard book={local()} />);fireEvent.click(screen.getByRole('button',{name:'Add to Reading List'}))
  await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Add to Reading List'}) as HTMLButtonElement).disabled,false))
  assert.deepEqual(saved.getState().readingList,[]);assert.equal(screen.queryByRole('button',{name:'In Reading List ✓'}),null)
})
parity('saving while session changes cannot populate the new account',['session','logout','saved-linked'],async()=>{
  deferred=()=>{};mount(<BookCard book={global()} />);fireEvent.click(screen.getByRole('button',{name:'Add to Reading List'}));await waitFor(()=>assert.ok(calls.find(c=>c.method==='POST')))
  await act(async()=>{localStorage.setItem('luminar_token','new-session');auth.setState({token:'new-session'});saved.getState().clearUserData();deferred!(Response.json({target_key:'OL1W'}))})
  assert.deepEqual(saved.getState().readingList,[])
})
parity('personal URL preserves library logo and catalogue despite stale remembered library',['logo','profile','libraries','reload','header','deep-links'],()=>{
  mount(<><Header/><AccountProfilePage/></>,`/account/profile?patron_library=${a}`)
  assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),`/libraries/${a}`)
  assert.equal(screen.getByRole('link',{name:'Browse Books'}).getAttribute('href'),`/libraries/${a}/catalogue`)
  assert.equal(screen.getByRole('link',{name:'Reading list'}).getAttribute('href'),`/reading-list?patron_library=${a}`)
  cleanup()
  for(const path of ['/invitations','/libraries','/libraries/register']){
    mount(<Header/>,`${path}?patron_library=${a}`)
    assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),`/libraries/${a}`)
    assert.equal(screen.getByRole('link',{name:'Browse Books'}).getAttribute('href'),`/libraries/${a}/catalogue`)
    cleanup()
  }
})
parity('global URL ignores remembered and forged query contexts',['logo','deep-links'],()=>{
  assert.equal(productLibraryId('/','?patron_library='+a),null);assert.equal(productLibraryId('/catalog','?patron_library='+a),null)
  assert.equal(productLibraryId(`/libraries/${a}/books/${bid}`,'?patron_library='+b),a)
  assert.equal(productLibraryId('/reading-list','?patron_library=bad'),null)
  assert.equal(withPatronContext('/platform',a),'/platform');assert.equal(withPatronContext('/staff/libraries/'+b,a),'/staff/libraries/'+b)
})
parity('saved local-only deep link and revoked target remain safe',['saved-local','reading-list','empty'],async()=>{
  items=[{target_key:`local:${a}:${bid}`,target_type:'LIBRARY_BOOK',library_id:a,library_book_id:bid,title:'Local saved',authors:'Ada',accessible:true},{target_key:`local:${b}:${bid}`,target_type:'LIBRARY_BOOK',title:'Unavailable library book',accessible:false}]
  saved.setState({readingList:items.map(i=>i.target_key)});mount(<ReadingListPage/>,`/reading-list?patron_library=${a}`)
  await screen.findByRole('article',{name:'Local saved'});assert.ok(screen.getAllByRole('link').some(l=>l.getAttribute('href')===`/libraries/${a}/books/${bid}`))
  assert.ok(screen.getByRole('button',{name:'Remove from Reading List'}));assert.equal(screen.queryByRole('button',{name:'Request Book'}),null)
})
parity('global filter pagination uses server filters and does not invent a total',['catalogue','subjects','author','pagination'],async()=>{
  mount(<GlobalCatalogue/>, '/catalog?category=Networking&author=Ada')
  await screen.findAllByRole('article',{name:'Shared Atlas'});assert.ok(calls.some(c=>c.path.includes('category=Networking') && c.path.includes('author=Ada')))
  assert.equal(screen.queryByText(/of 5000000/),null)
  fireEvent.click(screen.getByRole('button',{name:'Next page'}));await screen.findByRole('article',{name:'Second slice'})
  assert.ok(calls.some(c=>c.path.includes('offset=20') && c.path.includes('category=Networking') && c.path.includes('author=Ada')))
})
parity('recommendation View All selects recommendation data',['view-all','for-you'],async()=>{
  mount(<GlobalCatalogue/>, '/catalog?view=for-you');await screen.findByRole('article',{name:'Shared Atlas'})
  assert.ok(calls.some(c=>c.path.startsWith('/recommendation-api/recommendations')));assert.equal(calls.some(c=>c.path.startsWith('/api/books/?')),false)
})
parity('personal back and global reset survive browser-style navigation',['history-nav','logo'],()=>{
  mount(<><Header/><Link to="/">Global home</Link></>,`/reading-list?patron_library=${a}`)
  fireEvent.click(screen.getByRole('link',{name:'Global home'}));assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),'/')
})
for(const context of ['GLOBAL','LIBRARY'] as const){
  parity(context+' shared navigation preserves only explicit return context',['header','know-more','graph','events','arrivals','profile'],()=>{
    const errors:string[]=[],originalError=console.error
    console.error=(...args)=>errors.push(args.map(String).join(' '))
    try{mount(<Header/>,context==='GLOBAL'?'/catalog':`/libraries/${a}/catalogue`)}finally{console.error=originalError}
    assert.equal(errors.some(error=>error.includes('same key')),false,'Notification and account children must have distinct keys')
    for(const [name,path] of [['Graph Lab','/experimental/kg'],['Events','/events'],['Know More','/llm']]){
      assert.equal(screen.getByRole('link',{name,exact:true}).getAttribute('href'),context==='GLOBAL'?path:name==='Events'?`/libraries/${a}/events`:`${path}?patron_library=${a}`)
    }
    assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),context==='GLOBAL'?'/':`/libraries/${a}`)
    fireEvent.click(screen.getByRole('button',{name:'Search the catalog'}))
    fireEvent.change(screen.getByRole('searchbox'),{target:{value:'networking'}})
    fireEvent.click(screen.getByRole('button',{name:'Search',exact:true}))
    assert.equal(screen.getByTestId('url').textContent,context==='GLOBAL'?'/search?q=networking':`/libraries/${a}/catalogue?search=networking`)
  })
  parity(context+' personal Reading List has shared selection, removal and safe detail navigation',['reading-list','saved-linked','ai','counter','deep-links'],async()=>{
    items=[{...record,target_key:'OL1W',target_type:'GLOBAL_WORK'}];saved.setState({readingList:['OL1W']})
    mount(<ReadingListPage/>,context==='GLOBAL'?'/reading-list':`/reading-list?patron_library=${a}`)
    await screen.findByRole('article',{name:'Shared Atlas'})
    assert.ok(screen.getAllByRole('link').some(l=>l.getAttribute('href')===(context==='GLOBAL'?'/book/OL1W':`/libraries/${a}/global-books/OL1W`)))
    assert.equal(screen.queryByRole('button',{name:'Request Book'}),null)
    fireEvent.click(screen.getByRole('button',{name:'Select Shared Atlas'}));assert.equal(assistant.getState().selected[0].work_id,'OL1W')
    fireEvent.click(screen.getByRole('button',{name:'In Reading List ✓'}));await waitFor(()=>assert.deepEqual(saved.getState().readingList,[]))
    assert.ok(calls.some(c=>c.method==='DELETE' && c.path.endsWith('/OL1W')))
  })
}
parity('late failed save cannot expose the old account error toast',['session','logout','errors'],async()=>{
  deferred=()=>{};mount(<><BookCard book={global()}/><ToastContainer/></>)
  fireEvent.click(screen.getByRole('button',{name:'Add to Reading List'}));await waitFor(()=>assert.ok(calls.find(c=>c.method==='POST')))
  await act(async()=>{localStorage.setItem('luminar_token','new-session');auth.setState({token:'new-session'});saved.getState().clearUserData();deferred!(Response.json({detail:'Late private save error'},{status:409}))})
  assert.equal(screen.queryByText('Late private save error'),null);assert.deepEqual(saved.getState().readingList,[])
})
