import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test,beforeEach,afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html lang="en"><head><title>Critical closure</title></head><body></body></html>',{url:'http://localhost:5173'})
class FormDataWithFiles extends dom.window.FormData {constructor(form?:HTMLFormElement){super(form);form?.querySelectorAll<HTMLInputElement>('input[type=file]').forEach(input=>{if(input.files?.[0])this.set(input.name,input.files[0])})}}
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,File:dom.window.File,FormData:FormDataWithFiles,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {BookEditor}=await import('../src/pages/LibraryInventory')
const {BookCover}=await import('../src/components/BookCover')
const {BookCoverArt}=await import('../src/components/BookCoverArt')
const {Header}=await import('../src/components/Header')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:store}=await import('../src/store/useInstitutionStore')
const {PALETTES}=await import('../src/data/books')
const a='11111111-1111-4111-8111-111111111111',bid='22222222-2222-4222-8222-222222222222',doc='33333333-3333-4333-8333-333333333333'
const original=globalThis.fetch
let calls:{path:string;method:string;body:any}[],failed:boolean
beforeEach(()=>{
  localStorage.clear();localStorage.setItem('luminar_token','critical-session');auth.setState({token:'critical-session',isAuthenticated:true,user:{user_id:1,email:'qa@example.com',role:'GENERAL_USER'}})
  store.setState({owner:'qa@example.com',session:'critical-session',activeId:a,loading:false,error:null,libraries:[{library_id:a,name:'QA',slug:'qa',description:null,library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',membership:{membership_id:a,library_id:a,user_id:1,role:'ADMIN',status:'ACTIVE',is_owner:true,joined_at:'2026-10-12T00:00:00Z'}}]})
  calls=[];failed=false
  globalThis.fetch=async(url,options={})=>{
    const path=String(url),method=options.method||'GET',body=options.body instanceof FormData?options.body:options.body?JSON.parse(String(options.body)):undefined;calls.push({path,method,body})
    if(path.endsWith('/assets'))return failed?Response.json({detail:'Upload unavailable'},{status:503}):Response.json({asset_id:doc,library_id:a,status:'READY',library_book_id:bid},{status:202})
    if(path.endsWith('/books')&&method==='POST')return Response.json({library_book_id:bid,library_id:a,title:body.title,subjects:body.subjects,authors:[],accession_number:'QA-000001',holding:body.create_physical_holding?{total_copies:body.copies}:null,book_format:body.create_physical_holding?'PHYSICAL_ONLY':'UNAVAILABLE'},{status:201})
    if(path.endsWith('/books/'+bid))return Response.json({library_book_id:bid,library_id:a,title:'Fixture',subjects:['Reference'],authors:[],accession_number:'QA-000001',holding:null,book_format:'DIGITAL_ONLY'})
    return Response.json({results:[],total:0})
  }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
const mount=(node:React.ReactNode,path='/')=>render(<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>)
function form(mode='Physical'){mount(<BookEditor libraryId={a} onSaved={()=>{}}/>);fireEvent.click(screen.getByRole('radio',{name:mode,exact:true}))}
function fill(){fireEvent.change(screen.getByLabelText('Title *'),{target:{value:'Fixture'}});fireEvent.change(screen.getByLabelText(/Subject \/ Genre/),{target:{value:'Reference'}})}
function file(){fireEvent.change(screen.getByLabelText('Upload soft copy *'),{target:{files:[new File(['%PDF fixture'],'fixture.pdf',{type:'application/pdf'})]}})}

test('test_staff_catalog_route_is_staff_catalogue',()=>{mount(<Header/>,`/staff/libraries/${a}`);assert.equal(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),`/staff/libraries/${a}/catalogue`)})
test('test_staff_catalog_route_contains_library_uuid',()=>{mount(<Header/>,`/staff/libraries/${a}/inventory`);assert.match(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href')!,new RegExp(a))})
test('test_staff_catalog_does_not_use_global_catalogue',()=>{mount(<Header/>,`/staff/libraries/${a}`);assert.notEqual(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),'/catalog')})
test('test_staff_catalog_no_staff_library_query_hack',()=>{mount(<Header/>,`/reading-list?staff_library=${a}`);assert.ok(!screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href')!.includes('?'))})
test('test_global_catalog_still_global',()=>{mount(<Header/>,'/catalog');assert.equal(screen.getByRole('link',{name:'Catalog',exact:true}).getAttribute('href'),'/catalog');assert.equal(screen.getByRole('link',{name:'LuminaR home',exact:true}).getAttribute('href'),'/')})
test('test_patron_catalog_still_patron_scoped',()=>{store.setState({libraries:store.getState().libraries.map(l=>({...l,membership:{...l.membership!,role:'GENERAL_USER'}}))});mount(<Header/>,`/libraries/${a}`);assert.equal(screen.getByRole('link',{name:'Browse Books',exact:true}).getAttribute('href'),`/libraries/${a}/catalogue`)})
test('test_add_book_has_three_way_format_control',()=>{form();assert.ok(screen.getByRole('group',{name:'Format'}));assert.ok(screen.getByRole('radiogroup',{name:'Book format'}));assert.equal(screen.getAllByRole('radio').length,3)})
for(const mode of ['Physical','Online','Physical + Online'])test(`test_format_${mode.toLowerCase().replaceAll(' ','_').replace('+','and')}_exclusive`,()=>{form(mode);assert.equal(screen.getAllByRole('radio').filter(r=>(r as HTMLInputElement).checked).length,1);assert.ok((screen.getByRole('radio',{name:mode,exact:true}) as HTMLInputElement).checked)})
test('test_physical_shows_physical_fields',()=>{form();assert.ok(screen.getByLabelText('Quantity *'));assert.ok(screen.getByLabelText('Shelf / Location'));assert.ok(screen.getByLabelText('Call Number'))})
test('test_physical_hides_online_required_fields',()=>{form();assert.equal(screen.queryByLabelText('Upload soft copy *'),null)})
test('test_online_shows_upload',()=>{form('Online');assert.ok((screen.getByLabelText('Upload soft copy *') as HTMLInputElement).required);assert.ok(screen.getByLabelText('Visibility'))})
test('test_online_does_not_require_quantity',()=>{form('Online');assert.equal(screen.queryByLabelText('Quantity *'),null)})
test('test_online_does_not_require_shelf',()=>{form('Online');assert.equal(screen.queryByLabelText('Shelf / Location'),null);assert.equal(screen.queryByLabelText('Call Number'),null)})
test('test_both_shows_physical_and_online_fields',()=>{form('Physical + Online');assert.ok(screen.getByLabelText('Quantity *'));assert.ok(screen.getByLabelText('Upload soft copy *'))})
test('test_online_does_not_create_holding',async()=>{form('Online');fill();file();fireEvent.submit(screen.getByRole('button',{name:'Save New Book'}).closest('form')!);await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/books/'+bid))));const payload=calls.find(c=>c.method==='POST'&&c.path.endsWith('/books'))!.body;assert.equal(payload.copies,0);assert.equal(payload.create_physical_holding,false);assert.equal(payload.shelf_location,null);const upload=calls.find(c=>c.path.endsWith('/assets'))!.body;assert.equal(upload.get('library_book_id'),bid)})
test('test_online_failure_preserves_book_and_retry_does_not_duplicate',async()=>{form('Physical + Online');fill();file();failed=true;fireEvent.submit(screen.getByRole('button',{name:'Save New Book'}).closest('form')!);await screen.findByRole('alert');assert.match(screen.getByRole('alert').textContent!,/Book added as Physical/);failed=false;fireEvent.submit(screen.getByRole('button',{name:'Retry Online Upload'}).closest('form')!);await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/books/'+bid))));assert.equal(calls.filter(c=>c.method==='POST'&&c.path.endsWith('/books')).length,1)})

function cover(title='The Tower',author?:string,variant:any='split'){return render(<BookCover title={title} author={author} paletteIndex={6} variant={variant}/>)}
test('test_book_cover_title_has_no_background_box',()=>{const r=cover();assert.equal(window.getComputedStyle(r.container.querySelector('.book-cover-title')!).backgroundColor,'rgba(0, 0, 0, 0)');assert.equal(r.container.querySelector('.book-cover-text-scrim'),null)})
test('test_book_cover_author_has_no_background_box',()=>{const r=cover('The Tower','Author');assert.equal(window.getComputedStyle(r.container.querySelector('.book-cover-author')!).backgroundColor,'rgba(0, 0, 0, 0)')})
test('test_book_cover_no_title_pseudo_backplate',()=>{const r=cover();assert.equal(r.container.querySelector('.book-cover-copy')!.getAttribute('style'),null);assert.equal(r.container.querySelector('.book-cover-text-scrim'),null)})
for(const [name,title] of [['long','Samuel Huntington, President of Congress Longer Than Expected'],['short','Money 1988'],['unicode','靈山 = Ling Shan']])test(`test_book_cover_${name}_title_no_box`,()=>{const r=cover(title);assert.equal(r.container.querySelector('.book-cover-title')!.textContent,title);assert.equal(window.getComputedStyle(r.container.querySelector('.book-cover-title')!).backgroundColor,'rgba(0, 0, 0, 0)')})
test('test_book_cover_multiple_authors_no_box',()=>{const r=cover('Becoming Muhammad Ali','James Patterson; Kwame Alexander');assert.equal(r.container.querySelector('.book-cover-author')!.textContent,'James Patterson; Kwame Alexander')})
test('test_book_cover_missing_author_no_empty_box',()=>{const r=cover();assert.equal(r.container.querySelector('.book-cover-author'),null)})
test('test_book_cover_original_palette_typography',()=>{for(let index=0;index<PALETTES.length;index++){const r=mount(<BookCover title="Original palette" author="Author" paletteIndex={index} variant="split"/>);const art=r.container.firstElementChild as HTMLElement;const probe=document.createElement('span');probe.style.color=PALETTES[index].fg;assert.equal(art.style.color,probe.style.color);assert.equal(art.querySelector('.book-cover-region-type'),null);assert.equal(art.querySelectorAll('.book-cover-title').length,1);cleanup()}})
test('test_book_cover_geometry_behind_text',()=>{const r=cover();const art=r.container.firstElementChild!;assert.ok(art.children[0].classList.contains('absolute'));assert.ok(art.children[1].classList.contains('book-cover-content'));assert.equal(art.querySelector('.book-cover-text-scrim'),null)})
test('test_book_cover_global_local_same_renderer',()=>{const r=render(<><BookCoverArt title="Global book" author="" seed={1}/><BookCoverArt title="Local book" author="" seed={2}/></>);assert.equal(r.container.querySelectorAll('.book-cover-art').length,2);assert.equal(r.container.querySelectorAll('.book-cover-author').length,0)})
test('test_book_cover_mobile_no_backplate',()=>{const r=cover('Logical Aspects of Computational Linguistics','Author');assert.equal(r.container.querySelector('.book-cover-text-scrim'),null);assert.equal(r.container.querySelectorAll('.book-cover-copy [style*="background"]').length,0)})
