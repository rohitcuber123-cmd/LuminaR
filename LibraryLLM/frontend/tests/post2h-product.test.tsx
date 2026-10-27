import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import { readFileSync } from 'node:fs'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { DisplayBook } from '../src/lib/libraryCatalogue'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,cleanup,fireEvent}=await import('@testing-library/react')
const {MemoryRouter,Routes,Route}=await import('react-router-dom')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:store}=await import('../src/store/useInstitutionStore')
const {useLibraryStore:lists}=await import('../src/store/useLibraryStore')
const {resolveLibraryBookCapabilities:resolve}=await import('../src/lib/libraryBookCapabilities')
const {BookCard}=await import('../src/components/BookCard')
const {CatalogueBookActions}=await import('../src/components/CatalogueBookActions')
const {BookDetailView}=await import('../src/components/BookDetailView')
const {ReadingListPage}=await import('../src/pages/ReadingListPage')
const {LibraryAssetDetailPage}=await import('../src/pages/LibraryAssets')
const a='11111111-1111-4111-8111-111111111111',bid='22222222-2222-4222-8222-222222222222',asset='33333333-3333-4333-8333-333333333333'
const membership={library_id:a,membership_id:bid,user_id:1,role:'GENERAL_USER' as const,status:'ACTIVE' as const,is_owner:false,joined_at:'2026-10-14'}
function book(physical=false):DisplayBook{return {display_id:bid,library_id:a,library_book_id:bid,global_work_id:null,title:'CN',authors:['Author'],subjects:['Networking'],source:'LIBRARY',owned_by_current_library:true,cover_url:null,has_physical:physical,has_online:true,book_format:physical?'PHYSICAL_AND_DIGITAL':'DIGITAL_ONLY',online_asset_id:asset,shelf_location:physical?'LIT-02':null,circulation_status:physical?'CIRCULATING':null,requestable_count:physical?1:null,user_request_state:null,user_reservation_state:null,user_loan_state:null,actions:{request:physical,reserve:false,cancel_request:false,cancel_reservation:false}}}
let fetchBefore:typeof fetch,calls:string[]
beforeEach(()=>{localStorage.clear();localStorage.setItem('luminar_token','current');auth.setState({token:'current',isAuthenticated:true,user:{user_id:1,email:'qa@example.com',name:'Patron',role:'GENERAL_USER'}});store.setState({session:'current',libraries:[{library_id:a,name:'TEST',slug:'test',library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',description:null,membership}],activeId:a,patronLibraryId:a,staffLibraryId:null,loading:false,error:null});lists.setState({readingList:[]});calls=[];fetchBefore=globalThis.fetch;globalThis.fetch=async(input)=>{calls.push(String(input));return Response.json({results:[],total:0})}})
afterEach(()=>{cleanup();globalThis.fetch=fetchBefore})
function card(value=book()){render(<MemoryRouter><BookCard book={value}/></MemoryRouter>);const more=screen.queryByRole('button',{name:/More discovery actions/});if(more)fireEvent.click(more)}
function detail(value=book()){render(<MemoryRouter><BookDetailView book={value} backPath={'/libraries/'+a} physicalActions={<CatalogueBookActions book={value} changed={()=>{}}/>}/></MemoryRouter>)}
test('test_online_only_card_read_online',()=>{card();assert.equal(screen.getByRole('link',{name:'Read Online'}).getAttribute('href'),`/libraries/${a}/resources/${asset}?book=${bid}&open=1`);assert.ok(screen.getByText('Available online'))})
test('test_online_only_card_no_request_book',()=>{card();assert.equal(screen.queryByRole('button',{name:'Request Book'}),null);assert.equal(screen.queryByText(/Shelf/),null)})
test('test_online_only_detail_read_online',()=>{detail();assert.ok(screen.getByRole('link',{name:'Read Online'}))})
for (const surface of ['card','detail']) test(`online-only ${surface} offers Know More without a loan or global work`,()=>{
  if(surface==='card')card();else detail()
  const url=new URL(screen.getByRole('link',{name:'Know More',exact:true}).getAttribute('href')!,'http://localhost')
  assert.equal(url.pathname,'/llm');assert.equal(url.searchParams.get('library_id'),a)
  assert.equal(url.searchParams.get('library_book'),bid);assert.equal(url.searchParams.get('library_asset'),asset)
  assert.equal(url.searchParams.get('patron_library'),a)
})
test('physical-only book does not offer online Know More',()=>{const b=book(true);b.has_online=false;b.book_format='PHYSICAL_ONLY';b.online_asset_id=null;card(b);assert.equal(screen.queryByRole('link',{name:'Know More'}),null)})
test('book with physical and online copies offers Know More',()=>{card(book(true));assert.ok(screen.getByRole('link',{name:'Know More'}))})
test('multiple online copies require choosing a source for Know More',()=>{const b=book();b.online_asset_id=null;card(b);assert.equal(screen.getByRole('link',{name:'Know More'}).getAttribute('href'),`/libraries/${a}/books/${bid}#digital-resources`)})
test('test_online_only_detail_no_physical_fields',()=>{detail();for(const label of ['Copies','Shelf / Location','Call number','Circulation status'])assert.equal(screen.queryByText(label),null);assert.equal(screen.queryByRole('button',{name:'Request Book'}),null)})
test('test_both_card_request_and_read',()=>{card(book(true));assert.ok(screen.getByRole('button',{name:'Request Book'}));assert.ok(screen.getByRole('link',{name:'Read Online'}));assert.ok(screen.getByText('Physical + Online'))})
test('test_both_detail_request_and_read',()=>{detail(book(true));assert.ok(screen.getByRole('button',{name:'Request Book'}));assert.ok(screen.getByRole('link',{name:'Read Online'}))})
test('test_both_zero_physical_still_read_online',()=>{const b=book(true);b.requestable_count=0;b.actions={...b.actions,request:false,reserve:true};card(b);assert.ok(screen.getByRole('button',{name:'Join Waitlist'}));assert.ok(screen.getByRole('link',{name:'Read Online'}))})
test('test_both_online_access_independent_of_physical_availability',()=>{const b=book(true);b.circulation_status='TEMPORARILY_UNAVAILABLE';b.requestable_count=0;b.actions.request=false;card(b);assert.ok(screen.getByRole('link',{name:'Read Online'}));assert.equal(screen.queryByRole('button',{name:'Request Book'}),null)})
test('test_staff_only_asset_no_patron_read_action',()=>{const b=book(true);b.has_online=false;b.online_asset_id=null;b.book_format='PHYSICAL_ONLY';card(b);assert.equal(screen.queryByRole('link',{name:'Read Online'}),null);assert.ok(screen.getByText('Physical',{exact:true}))})
test('test_multiple_assets_require_explicit_resource_choice',()=>{const b=book();b.online_asset_id=null;card(b);assert.equal(screen.getByRole('link',{name:'Read Online'}).getAttribute('href'),`/libraries/${a}/books/${bid}#digital-resources`)})
test('test_reading_list_uses_shared_book_capabilities',async()=>{globalThis.fetch=async()=>Response.json({items:[{target_key:`local:${a}:${bid}`,target_type:'LIBRARY_BOOK',library_id:a,library_book_id:bid,title:'CN',authors:'Author',accessible:true,library_book:book()}]});render(<MemoryRouter><ReadingListPage/></MemoryRouter>);assert.ok(await screen.findByRole('link',{name:'Read Online'}));assert.equal(screen.queryByRole('button',{name:'Request Book'}),null)})
test('test_reading_list_cached_metadata_cannot_authorize',async()=>{globalThis.fetch=async()=>Response.json({items:[{target_key:`local:${a}:${bid}`,target_type:'LIBRARY_BOOK',library_id:a,library_book_id:bid,title:'CN',authors:'Author'}]});render(<MemoryRouter><ReadingListPage/></MemoryRouter>);await screen.findByRole('article',{name:'CN'});assert.equal(screen.queryByRole('link',{name:'Read Online'}),null)})
test('test_no_stale_session_or_wrong_library_capabilities',()=>{assert.equal(resolve(book(),{...membership,library_id:bid}).canReadOnline,false);assert.equal(resolve(book(),{...membership,status:'REMOVED'}).canReadOnline,false);store.setState({session:'previous-account'});card();assert.equal(screen.queryByRole('link',{name:'Read Online'}),null)})
test('test_staff_cannot_receive_patron_read_actions',()=>{store.setState({libraries:[{...store.getState().libraries[0],membership:{...membership,role:'ADMIN',is_owner:true}}]});card();assert.equal(screen.queryByRole('link',{name:'Read Online'}),null)})
test('test_online_viewer_auto_opens_authorized_resource',async()=>{globalThis.fetch=async(input)=>{calls.push(String(input));return Response.json(String(input).endsWith('/preview')?{library_id:a,asset_id:asset,text:'Authorized member document'}:{library_id:a,asset_id:asset,library_book_id:bid,title:'CN',asset_type:'TXT',status:'READY',visibility:'MEMBERS',original_filename:'CN.txt',pages:1})};render(<MemoryRouter initialEntries={[`/libraries/${a}/resources/${asset}?book=${bid}&open=1`]}><Routes><Route path='/libraries/:libraryId/resources/:assetId' element={<LibraryAssetDetailPage/>}/></Routes></MemoryRouter>);assert.ok(await screen.findByText('Authorized member document'));assert.ok(calls.some(p=>p.endsWith('/preview')));assert.ok(screen.getByRole('button',{name:'Close document'}))})
test('test_viewer_checks_linked_book_before_content',async()=>{globalThis.fetch=async(input)=>{calls.push(String(input));return Response.json({library_id:a,asset_id:asset,library_book_id:asset,title:'CN',asset_type:'TXT',status:'READY',visibility:'MEMBERS'})};render(<MemoryRouter initialEntries={[`/libraries/${a}/resources/${asset}?book=${bid}&open=1`]}><Routes><Route path='/libraries/:libraryId/resources/:assetId' element={<LibraryAssetDetailPage/>}/></Routes></MemoryRouter>);await screen.findByText('This resource is no longer linked to the selected book.');assert.equal(calls.some(p=>p.endsWith('/preview')),false)})
for(const [name,file,pattern] of [
 ['test_staff_catalogue_status_uses_shared_select','src/components/CatalogueSurface.tsx',/LuminarSelect/],
 ['test_analytics_range_uses_shared_select','src/pages/LibraryAnalyticsPage.tsx',/LuminarSelect/],
 ['test_staff_library_selector_shared_select','src/components/LibrarySwitcher.tsx',/LuminarSelect/],
 ['test_home_uses_shared_book_capabilities','src/components/BookCard.tsx',/resolveLibraryBookCapabilities/],
 ['test_catalogue_uses_shared_book_capabilities','src/pages/LibraryCatalogue.tsx',/BookCard/],
 ['test_search_uses_shared_book_capabilities','src/components/GlobalCatalogue.tsx',/BookCard/],
 ['test_book_detail_uses_shared_book_capabilities','src/components/BookDetailView.tsx',/resolveLibraryBookCapabilities/],
] as const)test(name,()=>assert.match(readFileSync(new URL('../'+file,import.meta.url),'utf8'),pattern))
