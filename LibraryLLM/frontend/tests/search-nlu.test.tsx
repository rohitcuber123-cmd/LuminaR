import assert from 'node:assert/strict'
import {test,afterEach} from 'node:test'
import {registerHooks} from 'node:module'
import React from 'react'
import {JSDOM} from 'jsdom'
import {chooseSelect,selectedValue} from './select-control'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor}=await import('@testing-library/react')
const {SearchIntelligence,SearchModeControl}=await import('../src/components/SearchIntelligence')
const {searchOptions}=await import('../src/lib/searchNlu')
afterEach(cleanup)
const facets={results:[{subject:'Fiction',count:12}],capabilities:{rating:true,year:true,language:true,formats:['ONLINE','PHYSICAL','BOTH'],availability:true}}
test('search mode defaults to Smart and exposes all four modes',()=>{
 let value='';render(<SearchModeControl onChange={mode=>{value=mode}}/>)
 const control=screen.getByRole('combobox',{name:'Search mode'})
 assert.equal(selectedValue(control),'SMART')
 for(const mode of ['GENRE_SUBJECT','TITLE_AUTHOR','EXACT','SMART']){chooseSelect(control,mode,fireEvent);assert.equal(value,mode)}
})
test('chips reflect interpretation and removing a constraint preserves raw input',()=>{
 const params=new URLSearchParams({q:'fiction books about wizards rating above 4'});let change:string[]=[]
 render(<SearchIntelligence params={params} update={(k,v)=>{change=[k,v]}} facets={facets} interpretation={{mode:'SMART',chips:[{key:'subject',label:'Genre / Subject: Fiction'},{key:'topic',label:'Topic: wizards'},{key:'rating_min',label:'Rating: > 4'}],corrections:[]}}/>)
 fireEvent.click(screen.getByRole('button',{name:'Remove Rating: > 4'}))
 assert.deepEqual(change,['omit','rating_min']);assert.equal(params.get('q'),'fiction books about wizards rating above 4')
 assert.ok(screen.getByRole('button',{name:'Remove Topic: wizards'}))
})
test('rating format availability and sorting controls emit explicit server filters',()=>{
 const changes:Record<string,string>={};render(<SearchIntelligence params={new URLSearchParams()} update={(k,v)=>{changes[k]=v}} facets={facets}/>)
 fireEvent.click(screen.getByText('Search filters'))
 fireEvent.blur(screen.getByLabelText('Minimum rating'),{target:{value:'4.2'}})
 chooseSelect(screen.getByRole('combobox',{name:'Format filter'}),'ONLINE',fireEvent)
 chooseSelect(screen.getByRole('combobox',{name:'Availability filter'}),'REQUESTABLE',fireEvent)
 chooseSelect(screen.getByRole('combobox',{name:'Search sort'}),'NEWEST',fireEvent)
 assert.deepEqual(changes,{rating_min:'4.2',format:'ONLINE',availability:'REQUESTABLE',search_sort:'NEWEST'})
 const options=searchOptions(new URLSearchParams(changes))
 assert.equal(options.rating_min,4.2);assert.equal(options.sort,'NEWEST')
})
test('unsupported global year language and physical filters are absent',()=>{
 render(<SearchIntelligence params={new URLSearchParams()} update={()=>{}} facets={{...facets,capabilities:{...facets.capabilities,year:false,language:false,availability:false,formats:['ONLINE']}}}/>)
 assert.equal(screen.queryByLabelText('Published from'),null);assert.equal(screen.queryByLabelText('Language filter'),null)
 fireEvent.click(screen.getByRole('combobox',{name:'Format filter'}))
 assert.equal(screen.queryByRole('option',{name:'Physical',exact:true}),null)
})
test('correction and ambiguous subject suggestions are visible and actionable',()=>{
 let change:string[]=[];render(<SearchIntelligence tenant params={new URLSearchParams()} update={(k,v)=>{change=[k,v]}} facets={facets} interpretation={{mode:'SMART',chips:[],corrections:[{from:'fictin',to:'Fiction',kind:'typo'}],suggested_subject:'Fiction'}}/>)
 assert.ok(screen.getByRole('status').textContent?.includes('fictin'))
 fireEvent.click(screen.getByRole('button',{name:'Search as subject: Fiction'}));assert.deepEqual(change,['subject','Fiction'])
})
test('search controls pass structural axe checks',async()=>{
 const view=render(<main><SearchModeControl onChange={()=>{}}/><SearchIntelligence params={new URLSearchParams()} update={()=>{}} facets={facets}/></main>)
 const axe=await import('axe-core')
 const report=await axe.default.run(view.container,{rules:{'color-contrast':{enabled:false}}})
 assert.deepEqual(report.violations.map(v=>v.id),[])
})
test('V2A intent negative correction and graph concepts are visible without internals',()=>{
 let change:string[]=[]
 render(<SearchIntelligence params={new URLSearchParams()} update={(k,v)=>{change=[k,v]}} facets={facets} interpretation={{mode:'SMART',intent:'DISCOVER_TOPIC',intent_label:'Discover topic',related_concepts:['Deep learning','Machine learning'],chips:[{key:'exclude',label:'Exclude: Romance'}],corrections:[{from:'detectve',to:'Detective and mystery stories',kind:'typo'}]}}/>)
 assert.ok(screen.getByText('Intent: Discover topic'))
 assert.ok(screen.getByText(/Did you mean/))
 fireEvent.click(screen.getByText('Related concepts included'))
 assert.ok(screen.getByText('Deep learning · Machine learning'))
 fireEvent.click(screen.getByRole('button',{name:'Remove Exclude: Romance'}))
 assert.deepEqual(change,['omit','exclude'])
 assert.equal(screen.queryByText(/generation|vector score|node id/i),null)
})
test('zero results retain strict filters and chip removal reruns raw query through Global catalogue',async()=>{
 const {MemoryRouter}=await import('react-router-dom')
 const {GlobalCatalogue}=await import('../src/components/GlobalCatalogue')
 const {useAuthStore}=await import('../src/store/useAuthStore')
 localStorage.setItem('luminar_token','nlu-fixture')
 useAuthStore.setState({token:'nlu-fixture',isAuthenticated:true,user:{user_id:1,email:'nlu@example.com',role:'GENERAL_USER'}})
 const original=globalThis.fetch;const payloads:Record<string,unknown>[]=[]
 globalThis.fetch=async(input,init={})=>{
  const path=String(input)
  if(path.endsWith('/facets'))return Response.json(facets)
  if(path.includes('/categories'))return Response.json({categories:[]})
  if(path.endsWith('/search')){
   const body=JSON.parse(String(init.body));payloads.push(body)
   return Response.json({results:[],total_ranked_candidates:0,has_more:false,interpretation:{mode:'SMART',chips:[{key:'topic',label:'Topic: wizards'},...(!body.omit.includes('rating_min')?[{key:'rating_min',label:'Rating: > 4'}]:[])],corrections:[]}})
  }
  return Response.json({})
 }
 try{
  render(<MemoryRouter initialEntries={['/search?q=books+about+wizards+rating+above+4']}><GlobalCatalogue searchPage/></MemoryRouter>)
  await screen.findByText('No books match all selected filters.')
  assert.equal(payloads.length,1);assert.equal(payloads[0].query,'books about wizards rating above 4')
  fireEvent.click(screen.getByRole('button',{name:'Remove Rating: > 4'}))
  await waitFor(()=>assert.equal(payloads.length,2))
  assert.deepEqual(payloads[1].omit,['rating_min']);assert.equal(payloads[1].query,payloads[0].query)
  await waitFor(()=>assert.equal(screen.queryByRole('button',{name:'Remove Rating: > 4'}),null))
  assert.equal((screen.getByRole('combobox',{name:'Search by title, author or subject'}) as HTMLInputElement).value,'books about wizards rating above 4')
 }finally{cleanup();globalThis.fetch=original}
})
for(const path of ['/search?category=Fiction','/catalog?view=for-you&format=ONLINE'])test(`explicit filters execute shared search at ${path}`,async()=>{
 const {MemoryRouter}=await import('react-router-dom');const {GlobalCatalogue}=await import('../src/components/GlobalCatalogue')
 const {useAuthStore}=await import('../src/store/useAuthStore')
 localStorage.setItem('luminar_token','nlu-filter-fixture');useAuthStore.setState({token:'nlu-filter-fixture',isAuthenticated:true})
 const original=globalThis.fetch;const calls:{path:string;body?:Record<string,unknown>}[]=[]
 globalThis.fetch=async(input,init={})=>{
  const url=String(input);calls.push({path:url,body:init.body?JSON.parse(String(init.body)):undefined})
  if(url.endsWith('/facets'))return Response.json(facets)
  if(url.includes('/categories'))return Response.json({categories:[]})
  return Response.json({results:[],total_ranked_candidates:0,has_more:false})
 }
 try{
  render(<MemoryRouter initialEntries={[path]}><GlobalCatalogue searchPage={path.startsWith('/search')}/></MemoryRouter>)
  await screen.findByText('No books match all selected filters.')
  const search=calls.find(c=>c.path==='/search-api/search');assert.ok(search)
  assert.equal(search.body?.query,'');assert.equal(calls.some(c=>c.path.startsWith('/recommendation-api/')),false)
  assert.equal(path.includes('category')?search.body?.category:search.body?.format,path.includes('category')?'Fiction':'ONLINE')
 }finally{cleanup();globalThis.fetch=original}
})
