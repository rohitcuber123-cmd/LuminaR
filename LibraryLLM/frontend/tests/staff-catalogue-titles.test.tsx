import { chooseSelect, selectedValue } from './select-control'
import assert from 'node:assert/strict'
import {registerHooks} from 'node:module'
import {test,beforeEach,afterEach} from 'node:test'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,FormData:dom.window.FormData,File:dom.window.File,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,cleanup,act}=await import('@testing-library/react')
const {MemoryRouter,Routes,Route,useLocation}=await import('react-router-dom')
const {LibraryInventoryPage}=await import('../src/pages/LibraryInventory')
const {LibraryCataloguePage,LibraryCatalogueDetail}=await import('../src/pages/LibraryCatalogue')
const {LibraryAssetDetailPage}=await import('../src/pages/LibraryAssets')
const {BookCard}=await import('../src/components/BookCard')
const {LibraryBookTitleLink}=await import('../src/components/LibraryBookTitleLink')
const {Header}=await import('../src/components/Header')
const {LibrarySwitcher}=await import('../src/components/LibrarySwitcher')
const {WorkspaceRoute}=await import('../src/components/WorkspaceRoute')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:store}=await import('../src/store/useInstitutionStore')
const {usePlatformStore:platform}=await import('../src/store/usePlatformStore')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',bid='33333333-3333-4333-8333-333333333333',assetId='44444444-4444-4444-8444-444444444444'
URL.createObjectURL=()=> 'blob:authorized-fixture'
URL.revokeObjectURL=()=>{}
const original=globalThis.fetch
let calls:string[]
const library=(id:string)=>({library_id:id,name:id===a?'Library A':'Library B',slug:id,description:null,library_type:'PUBLIC_LIBRARY' as const,access_mode:'PUBLIC' as const,membership:{membership_id:id,library_id:id,user_id:1,role:'ADMIN' as const,status:'ACTIVE' as const,is_owner:true,joined_at:'2026-10-13T00:00:00Z'}})
const book=(id=a)=>({display_id:bid,library_id:id,library_book_id:bid,global_work_id:'OL1W',title:id===a?'Campus Workbook':'Other Library Book',authors:['Ada','Grace'],subjects:['Reference'],source:'LIBRARY' as const,owned_by_current_library:true,accession_number:'A-001',shelf_location:'Shelf A',circulation_status:'CIRCULATING',requestable_count:2,book_format:'PHYSICAL_AND_DIGITAL' as const,has_physical:true,has_online:true,cover_url:null,user_request_state:null,user_loan_state:null,user_reservation_state:null,actions:{request:false,reserve:false,cancel_request:false,cancel_reservation:false}})
const source=(id=a)=>({library_id:id,library_name:id===a?'Library A':'Library B',catalogue_source:'LIBRARY_LOCAL',local_book_count:1,capabilities:{physical_actions:false,reservations:false,local_search:true,global_discovery:false},circulation_state:'CANONICAL',discovery_notice:null})
const inventoryBook=()=>({...book(),isbn_10:null,isbn_13:'9780000000001',local_call_number:'REF-1',status:'ACTIVE',needs_review:false,holding:{total_copies:2,available_copies:2,shelf_location:'Shelf A'},availability:{requestable:2,circulation_status:'CIRCULATING'}})
const asset=()=>({asset_id:assetId,library_id:a,library_book_id:bid,linked_book_title:'Campus Workbook',title:'Safe workbook online',status:'READY',visibility:'STAFF_ONLY',asset_type:'PDF',media_type:'application/pdf',byte_size:900,original_filename:'safe.pdf',created_at:'2026-10-13T00:00:00Z',updated_at:'2026-10-13T00:00:00Z'})
beforeEach(()=>{
 localStorage.clear();localStorage.setItem('luminar_token','staff-catalogue-session')
 auth.setState({token:'staff-catalogue-session',isAuthenticated:true,user:{user_id:1,name:'QA',email:'qa@example.com',role:'GENERAL_USER'}})
 store.setState({owner:'qa@example.com',session:'staff-catalogue-session',activeId:a,staffLibraryId:a,patronLibraryId:null,workspace:'STAFF',loading:false,error:null,libraries:[library(a),library(b)]})
 platform.setState({session:'staff-catalogue-session',roles:[],loading:false,error:''})
 calls=[]
 globalThis.fetch=async(url,options)=>{
  const path=String(url);calls.push(path);const id=path.includes(b)?b:a
  if(path.endsWith('/context'))return Response.json({library:library(id),membership:library(id).membership})
  if(path.includes('/catalogue/books?'))return Response.json({source:source(id),results:[book(id)],total:1,has_more:false,offset:0,limit:20})
  if(path.includes('/catalogue/genres?'))return Response.json({source:source(id),results:[{subject:'Reference',count:1}],total:1,has_more:false,offset:0,limit:50})
  if(path.includes('/catalogue/books/'+bid))return Response.json({source:source(id),book:book(id)})
  if(path.includes('/inventory/books/'+bid))return Response.json(inventoryBook())
  if(path.includes('/inventory/books?'))return Response.json({results:[inventoryBook()],total:42,has_more:true,role:'ADMIN',lending_state:'CANONICAL'})
  if(path.endsWith('/assets/'+assetId+'/preview/pages/1'))return new Response(new Blob(['safe PNG preview'],{type:'image/png'}))
  if(path.endsWith('/assets/'+assetId+'/file'))return new Response(new Blob(['%PDF safe fixture'],{type:'application/pdf'}))
  if(path.endsWith('/assets/'+assetId))return Response.json(asset())
  if(path.includes('/assets?'))return Response.json({results:[asset()],total:1})
  if(path.endsWith('/assets')&&options?.method==='POST')return Response.json(asset(),{status:202})
  return Response.json({results:[],total:0,unread_count:0})
 }
})
afterEach(async()=>{await act(async()=>{await Promise.resolve()});cleanup();globalThis.fetch=original})
function Location(){const l=useLocation();return <output aria-label="Location">{l.pathname+l.search}</output>}
type StartLocation=string|{pathname:string;state:unknown}
function mount(node:React.ReactNode,path:StartLocation=`/staff/libraries/${a}/catalogue`){return render(<MemoryRouter initialEntries={[path]}>{node}<Location/></MemoryRouter>)}
function routes(path:StartLocation=`/staff/libraries/${a}/inventory`){return mount(<Routes><Route path="/staff/libraries/:libraryId/inventory" element={<LibraryInventoryPage/>}/><Route path="/staff/libraries/:libraryId/books/:bookId" element={<LibraryCatalogueDetail staff/>}/><Route path="/staff/libraries/:libraryId/assets/:assetId" element={<LibraryAssetDetailPage staff/>}/></Routes>,path)}
const inventory=async()=>{routes();return screen.findByRole('link',{name:'Campus Workbook'})}
const detail=async()=>{routes(`/staff/libraries/${a}/books/${bid}`);await screen.findByRole('button',{name:'Edit Book'});await screen.findByRole('link',{name:'Read Online'})}
const catalogue=async()=>{mount(<LibraryCataloguePage staff/>);return screen.findByRole('article',{name:'Campus Workbook'})}

test('test_staff_inventory_title_is_link',async()=>{assert.equal((await inventory()).tagName,'A')})
test('test_staff_inventory_title_uses_library_book_id',async()=>{assert.equal((await inventory()).getAttribute('href'),`/staff/libraries/${a}/books/${bid}`)})
test('test_staff_inventory_title_opens_staff_book_detail',async()=>{fireEvent.click(await inventory());await screen.findByRole('button',{name:'Edit Book'});assert.equal(screen.getByLabelText('Location').textContent,`/staff/libraries/${a}/books/${bid}`)})
test('test_staff_title_does_not_open_patron_workspace',async()=>{fireEvent.click(await inventory());await screen.findByRole('button',{name:'Manage Stock'});assert.equal(document.querySelector(`a[href^="/libraries/${a}/books/"]`),null)})
test('test_staff_book_detail_format_visible',async()=>{await detail();assert.ok(screen.getByText('Physical + Online'));assert.ok(screen.getByText('Requestable quantity'))})
test('test_staff_book_detail_online_asset_visible',async()=>{await detail();assert.ok(screen.getByRole('link',{name:'Safe workbook online'}));assert.ok(screen.getByText(/Staff only/));assert.ok(calls.some(p=>p.includes('/assets?')&&!p.includes('visibility=MEMBERS')))})
test('test_staff_book_detail_read_online',async()=>{await detail();fireEvent.click(screen.getByRole('link',{name:'Read Online'}));await screen.findByRole('button',{name:'Close document'});assert.equal(screen.getByLabelText('Location').textContent,`/staff/libraries/${a}/assets/${assetId}?book=${bid}&open=1`);assert.ok(calls.some(p=>p.endsWith('/preview/pages/1')))})
test('test_staff_book_detail_add_online_copy',async()=>{await detail();fireEvent.click(screen.getByRole('button',{name:'Add Online Copy'}));assert.ok(screen.getByRole('dialog'));assert.ok(screen.getByLabelText('Document file'));assert.equal(document.getElementById(screen.getByLabelText('Visibility').id+'-native')!.getAttribute('name'),'visibility')})
test('test_digital_asset_linked_book_is_clickable',async()=>{routes(`/staff/libraries/${a}/assets/${assetId}`);const link=await screen.findByRole('link',{name:'Campus Workbook'});assert.equal(link.getAttribute('href'),`/staff/libraries/${a}/books/${bid}`);fireEvent.click(link);await screen.findByRole('button',{name:'Edit Book'})})
test('test_patron_book_title_preserves_patron_context',()=>{store.setState({libraries:store.getState().libraries.map(l=>({...l,membership:{...l.membership!,role:'GENERAL_USER'}}))});mount(<BookCard book={book()}/>,`/libraries/${a}/catalogue`);assert.equal(screen.getByRole('heading',{name:'Campus Workbook',exact:true}).closest('a')!.getAttribute('href'),`/libraries/${a}/books/${bid}`)})
test('test_global_book_title_preserves_global_context',()=>{mount(<BookCard book={{...book(),source:'GLOBAL',library_id:'',library_book_id:null,owned_by_current_library:false}}/>,'/catalog');assert.equal(screen.getByRole('heading',{name:'Campus Workbook',exact:true}).closest('a')!.getAttribute('href'),'/book/OL1W')})
test('test_book_title_keyboard_accessible',()=>{mount(<LibraryBookTitleLink libraryId={a} bookId={bid} staff title="Campus Workbook"/>);const link=screen.getByRole('link');link.focus();assert.equal(document.activeElement,link);assert.equal(link.tabIndex,0);assert.ok(link.classList.contains('book-title-link'))})
test('test_inventory_back_restores_state',async()=>{const path=`/staff/libraries/${a}/inventory?search=Campus&kind=local&format=PHYSICAL_AND_DIGITAL&state=active&page=1`;routes(path);fireEvent.click(await screen.findByRole('link',{name:'Campus Workbook'}));const back=await screen.findByRole('link',{name:'Back to Inventory'});assert.equal(back.getAttribute('href'),path);fireEvent.click(back);await screen.findByRole('link',{name:'Campus Workbook'});assert.equal((screen.getByLabelText('Search library inventory') as HTMLInputElement).value,'Campus');assert.equal(selectedValue(screen.getByLabelText('Record filter')),'local');assert.ok(screen.getByText('Page 2'));assert.ok(calls.some(p=>p.includes('offset=20')&&p.includes('format=PHYSICAL_AND_DIGITAL')))})
test('inventory Back never replays a creation action',async()=>{routes(`/staff/libraries/${a}/inventory?action=add&search=Campus`);await screen.findByRole('dialog');fireEvent.click(screen.getByRole('button',{name:'Close dialog'}));fireEvent.click(screen.getByRole('link',{name:'Campus Workbook'}));assert.equal((await screen.findByRole('link',{name:'Back to Inventory'})).getAttribute('href'),`/staff/libraries/${a}/inventory?search=Campus`)})
test('book detail rejects foreign or malformed Inventory return state',async()=>{for(const inventoryReturnTo of [`/staff/libraries/${b}/inventory`,{path:'/catalog'}]){routes({pathname:`/staff/libraries/${a}/books/${bid}`,state:{inventoryReturnTo}});await screen.findByRole('button',{name:'Edit Book'});assert.equal(screen.getByRole('link',{name:'Browse Books',exact:true}).getAttribute('href'),`/staff/libraries/${a}/catalogue`);cleanup()}})

test('test_staff_catalog_route_is_staff_catalogue',()=>{mount(<Header/>);assert.equal(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),`/staff/libraries/${a}/catalogue`)})
test('test_staff_catalog_not_inventory',()=>{mount(<Header/>);assert.notEqual(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),`/staff/libraries/${a}/inventory`)})
test('test_staff_catalog_not_global',async()=>{await catalogue();assert.equal(calls.some(p=>p.startsWith('/api/books')||p.startsWith('/search-api')),false)})
test('test_staff_catalog_uses_selected_library',async()=>{await catalogue();assert.ok(calls.filter(p=>p.includes('/catalogue/')).every(p=>p.includes(a)&&p.includes('staff=true')));assert.equal(screen.queryByText('Other Library Book'),null)})
test('test_staff_catalog_reuses_library_catalogue_surface',async()=>{await catalogue();assert.ok(document.querySelector('.product-catalogue .product-book-card .book-cover-art'));assert.equal(document.querySelector('.inventory-table'),null)})
test('test_staff_catalog_hides_patron_request_actions',async()=>{await catalogue();assert.equal(screen.queryByRole('button',{name:/Request Book|Join Waitlist/}),null);assert.ok(screen.getAllByRole('heading',{level:3}).find(heading=>heading.closest('a')))})
test('test_staff_catalog_title_opens_staff_book_detail',async()=>{await catalogue();assert.equal(screen.getByRole('heading',{name:'Campus Workbook',exact:true}).closest('a')!.getAttribute('href'),`/staff/libraries/${a}/books/${bid}`)})
test('test_staff_catalog_physical_online_badges',async()=>{await catalogue();assert.ok(screen.getByText('Physical + Online'));assert.ok(screen.getByText('Shelf Shelf A'))})
test('test_staff_catalog_switch_library',async()=>{mount(<Routes><Route path="/staff/libraries/:libraryId/*" element={<WorkspaceRoute staff><LibrarySwitcher staff/><LibraryCataloguePage staff/></WorkspaceRoute>}/></Routes>);await screen.findByRole('article',{name:'Campus Workbook'});chooseSelect(screen.getByLabelText('Switch staff library'),b,fireEvent);await screen.findByRole('article',{name:'Other Library Book'});assert.equal(screen.queryByRole('article',{name:'Campus Workbook'}),null);assert.equal(store.getState().activeId,b);assert.ok(calls.some(p=>p.includes(b+'/catalogue/books')&&p.includes('staff=true')))})
test('test_staff_inventory_remains_separate',async()=>{await inventory();assert.ok(document.querySelector('.inventory-table'));assert.equal(document.querySelector('.product-catalogue'),null)})
test('test_staff_explicit_global_catalogue_action',async()=>{await catalogue();assert.equal(screen.getByRole('link',{name:'Browse Global Catalogue'}).getAttribute('href'),'/catalog')})
test('test_patron_catalog_route_unchanged',()=>{store.setState({libraries:store.getState().libraries.map(l=>({...l,membership:{...l.membership!,role:'GENERAL_USER'}}))});mount(<Header/>,`/libraries/${a}`);assert.equal(screen.getByRole('link',{name:'Browse Books',exact:true}).getAttribute('href'),`/libraries/${a}/catalogue`)})
test('test_global_catalog_route_unchanged',()=>{mount(<Header/>,'/catalog');assert.equal(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),'/catalog')})
