import assert from 'node:assert/strict'
import {test,afterEach} from 'node:test'
import {registerHooks} from 'node:module'
import React,{useState} from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5174'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,HTMLElement:dom.window.HTMLElement,HTMLInputElement:dom.window.HTMLInputElement,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const {render,screen,fireEvent,cleanup,waitFor,act}=await import('@testing-library/react')
const {SearchAutocomplete}=await import('../src/components/SearchAutocomplete')
const {SearchClarification}=await import('../src/components/SearchClarification')
const {SearchIntelligence}=await import('../src/components/SearchIntelligence')
const {useAuthStore}=await import('../src/store/useAuthStore')
const original=globalThis.fetch
afterEach(()=>{cleanup();globalThis.fetch=original;localStorage.clear();sessionStorage.clear()})
function login(){localStorage.setItem('luminar_token','interaction-fixture');localStorage.setItem('luminar_user',JSON.stringify({user_id:1,email:'fixture@example.com',role:'GENERAL_USER'}));useAuthStore.setState({token:'interaction-fixture',isAuthenticated:true})}
const item=(display:string)=>({id:'issued-'+display,type:'SUBJECT',display,insert_text:display,match_kind:'PREFIX'})
function Field({scope={},onSelect=()=>{},mode='SMART'}:{scope?:{libraryId?:string;staff?:boolean};onSelect?:(s:string)=>void;mode?:string}){const [value,setValue]=useState('');return <SearchAutocomplete value={value} onChange={setValue} onSelect={onSelect} mode={mode} scope={scope} label="Search catalogue"/>}
const box=()=>screen.getByRole('combobox',{name:'Search catalogue'})
async function type(value:string){fireEvent.focus(box());fireEvent.change(box(),{target:{value}})}

test('debounced bounded requests carry the current library/workspace and keyboard selection is server verified',async()=>{
 login();const calls:{url:string;body:any}[]=[];let selected=''
 globalThis.fetch=async(url,options={})=>{calls.push({url:String(url),body:options.body?JSON.parse(String(options.body)):null});return Response.json(options.method==='POST'?{insert_text:'Neural Networks'}:{suggestions:[item('Neural Networks'),item('Networks')]})}
 render(<Field scope={{libraryId:'A',staff:true}} onSelect={v=>{selected=v}}/>);await type('ne')
 await screen.findByRole('option',{name:/Neural Networks/});assert.match(calls[0].url,/library_id=A/);assert.match(calls[0].url,/staff=true/);assert.match(calls[0].url,/limit=8/)
 fireEvent.keyDown(box(),{key:'ArrowDown'});assert.equal(box().getAttribute('aria-activedescendant'),screen.getAllByRole('option')[0].id)
 fireEvent.keyDown(box(),{key:'ArrowUp'});assert.equal(screen.getAllByRole('option')[1].getAttribute('aria-selected'),'true')
 fireEvent.keyDown(box(),{key:'ArrowDown'});fireEvent.keyDown(box(),{key:'Enter'})
 await waitFor(()=>assert.equal(selected,'Neural Networks'));assert.equal(calls.at(-1)!.body.suggestion_id,'issued-Neural Networks');assert.equal(screen.queryByRole('listbox'),null)
})

test('late response from previous prefix cannot replace the current suggestions',async()=>{
 login();let first:((r:Response)=>void)|undefined
 globalThis.fetch=async(url)=>String(url).includes('q=neur')?new Promise(resolve=>{first=resolve}):Response.json({suggestions:[item('Detective Fiction')]})
 render(<Field/>);await type('neur');await waitFor(()=>assert.ok(first));await type('dete');await screen.findByRole('option',{name:/Detective Fiction/})
 await act(async()=>first!(Response.json({suggestions:[item('Old private title')]})))
 assert.equal(screen.queryByText('Old private title'),null);assert.ok(screen.getByRole('option',{name:/Detective Fiction/}))
})

test('library and workspace switch hide old suggestions before new response',async()=>{
 login();globalThis.fetch=async()=>Response.json({suggestions:[item('Private Orchid')]})
 const view=render(<Field scope={{libraryId:'A'}}/>);await type('pri');await screen.findByRole('option',{name:/Private Orchid/})
 globalThis.fetch=async()=>new Promise(()=>{});view.rerender(<Field scope={{libraryId:'B',staff:true}}/>);assert.equal(screen.queryByText('Private Orchid'),null)
})

test('account switch cancels pending selection and prevents stale search',async()=>{
 login();let selected=false,resolveSelect:((r:Response)=>void)|undefined
 globalThis.fetch=async(_,options={})=>options.method==='POST'?new Promise(resolve=>{resolveSelect=resolve}):Response.json({suggestions:[item('Private Orchid')]})
 render(<Field scope={{libraryId:'A'}} onSelect={()=>{selected=true}}/>);await type('pri');fireEvent.click(await screen.findByRole('option',{name:/Private Orchid/}));await waitFor(()=>assert.ok(resolveSelect))
 act(()=>useAuthStore.setState({token:'different-account'}));await act(async()=>resolveSelect!(Response.json({insert_text:'Private Orchid'})))
 assert.equal(selected,false);assert.equal(screen.queryByRole('listbox'),null)
})

test('Escape and Tab close the popup without trapping focus or choosing a result',async()=>{
 login();let selected=false;globalThis.fetch=async()=>Response.json({suggestions:[item('Fiction')]})
 render(<Field onSelect={()=>{selected=true}}/>);await type('fi');await screen.findByRole('option');fireEvent.keyDown(box(),{key:'Escape'});assert.equal(box().getAttribute('aria-expanded'),'false')
 fireEvent.focus(box());await screen.findByRole('option');fireEvent.keyDown(box(),{key:'ArrowDown'});fireEvent.keyDown(box(),{key:'Tab'});assert.equal(screen.queryByRole('listbox'),null);assert.equal(selected,false)
})

test('IME composition suppresses suggestions and Enter selection until composition ends',async()=>{
 login();let calls=0;globalThis.fetch=async()=>{calls++;return Response.json({suggestions:[item('Fiction')]})}
 render(<Field/>);fireEvent.focus(box());fireEvent.compositionStart(box());fireEvent.change(box(),{target:{value:'fiction'}});fireEvent.keyDown(box(),{key:'Enter',isComposing:true})
 await act(async()=>new Promise(r=>setTimeout(r,260)));assert.equal(calls,0);assert.equal(screen.queryByRole('listbox'),null)
 fireEvent.compositionEnd(box());await screen.findByRole('option');assert.equal(calls,1)
})

test('Exact mode and offline suggestions preserve normal input',async()=>{
 login();let calls=0;globalThis.fetch=async()=>{calls++;throw new Error('offline')}
 const view=render(<Field mode="EXACT"/>);await type('Python 3');await act(async()=>new Promise(r=>setTimeout(r,250)));assert.equal(calls,0)
 view.rerender(<Field/>);await waitFor(()=>assert.equal(calls,1));assert.equal((box() as HTMLInputElement).value,'Python 3');assert.equal(screen.queryByRole('listbox'),null)
})

const clarification={clarification_id:'server-choice',decision_type:'INCOMPLETE',question:'What rating should these books be above?',original_query:'fiction rating above',search_mode:'SMART' as const,expires_at:'future',candidate_choices:[{choice_id:'issued-rating',label:'Apply rating',input_type:'number' as const,minimum:0,maximum:5}]}
test('numeric clarification sends only issued IDs and operand; successful response refreshes interpretation',async()=>{
 login();let body:any,mode='';globalThis.fetch=async(_,options={})=>{body=JSON.parse(String(options.body));return Response.json({interpretation:{mode:'SMART',session:{active:true,expires_at:new Date(Date.now()+60000).toISOString()}}})}
 render(<SearchClarification clarification={clarification} scope={{libraryId:'A'}} sessionId="context" onResolved={m=>{mode=m}}/>);assert.ok((screen.getByRole('button',{name:'Apply rating'}) as HTMLButtonElement).disabled)
 fireEvent.change(screen.getByRole('spinbutton',{name:'Clarification value'}),{target:{value:'3'}});fireEvent.click(screen.getByRole('button',{name:'Apply rating'}));await waitFor(()=>assert.equal(mode,'SMART'))
 assert.equal(body.value,'3');assert.equal(body.choice_id,'issued-rating');assert.equal(body.query,'fiction rating above');assert.equal(body.library_id,'A');assert.equal(body.plan,undefined)
})

test('expired or rejected choice displays an error and does not refresh or hide existing query',async()=>{
 login();let changed=false;globalThis.fetch=async()=>Response.json({detail:'Search choice expired. Submit the query again.'},{status:410})
 render(<SearchClarification clarification={{...clarification,candidate_choices:[{choice_id:'x',label:'Keep rating > 4'}]}} onResolved={()=>{changed=true}}/>);fireEvent.click(screen.getByRole('button',{name:'Keep rating > 4'}));await screen.findByRole('alert');assert.equal(changed,false);assert.ok(screen.getByText(clarification.question))
})

test('dismiss is a bounded delete and does not change accepted search',async()=>{
 login();let changed=false,url='';globalThis.fetch=async(input)=>{url=String(input);return Response.json({dismissed:true})}
 render(<SearchClarification clarification={clarification} scope={{libraryId:'A',staff:true}} onResolved={()=>{changed=true}}/>);fireEvent.click(screen.getByRole('button',{name:'Dismiss'}));await waitFor(()=>assert.match(url,/library_id=A&staff=true/));assert.equal(changed,false);assert.ok(screen.getByText(/Choice dismissed/))
})

test('Apply and Keep original are explicit correction actions with no hidden signals',async()=>{
 login();const ids:string[]=[];globalThis.fetch=async(_,options={})=>{ids.push(JSON.parse(String(options.body)).choice_id);return Response.json({interpretation:{mode:'SMART'}})}
 const correction={...clarification,decision_type:'EXECUTABLE_WITH_NOTICE',question:'Interpreted detectve fiction as Detective Fiction.',candidate_choices:[{choice_id:'apply',label:'Apply correction'},{choice_id:'keep',label:'Keep original wording'}]}
 const view=render(<SearchClarification clarification={correction} onResolved={()=>{}}/>);fireEvent.click(screen.getByRole('button',{name:'Keep original wording'}));await waitFor(()=>assert.deepEqual(ids,['keep']));await waitFor(()=>assert.equal((screen.getByRole('button',{name:'Apply correction'}) as HTMLButtonElement).disabled,false))
 fireEvent.click(screen.getByRole('button',{name:'Apply correction'}));await waitFor(()=>assert.deepEqual(ids,['keep','apply']));view.unmount()
})

test('changed autocomplete and clarification surfaces pass structural accessibility checks',async()=>{
 login();globalThis.fetch=async()=>Response.json({suggestions:[item('Neural Networks')]})
 const view=render(<main><Field/><SearchClarification clarification={clarification} onResolved={()=>{}}/></main>);await type('neur');await screen.findByRole('option')
 const axe=await import('axe-core');assert.deepEqual((await axe.default.run(view.container,{rules:{'color-contrast':{enabled:false}}})).violations.map(v=>v.id),[])
})

for(const denied of [true,false])test(`suggestion denial revalidates tenant context; membership revoked=${denied}`,async()=>{
 login();let detail:any,contextCalls=0
 const listener=(event:Event)=>{detail=(event as CustomEvent).detail};window.addEventListener('luminar-library-access-denied',listener)
 globalThis.fetch=async(url)=>{if(String(url).includes('/context')){contextCalls++;return Response.json(denied?{detail:'Current membership is required.'}: {library:{library_id:'A'}},{status:denied?403:200})}return Response.json({detail:'Not available'},{status:404})}
 try {render(<Field scope={{libraryId:'A'}}/>);await type('private');await waitFor(()=>assert.equal(contextCalls,1));await act(async()=>new Promise(r=>setTimeout(r,20)));assert.equal(screen.queryByRole('listbox'),null);assert.equal(!!detail,denied);if(denied){assert.equal(detail.library_id,'A');assert.equal(detail.session,'interaction-fixture')}}finally{window.removeEventListener('luminar-library-access-denied',listener)}
})

test('KG disclosure appears only with an actual nonempty concept list; preference remains distinct',()=>{
 const interpretation={mode:'SMART' as const,chips:[{key:'rating_min',label:'Rating: > 4'}],corrections:[],preference:'Introductory / beginner (preference)',related_concepts:[] as string[]}
 const view=render(<SearchIntelligence params={new URLSearchParams()} update={()=>{}} facets={null} interpretation={interpretation}/>);assert.equal(screen.queryByText('Related concepts included'),null);assert.ok(screen.getByText(/Preference:/).className.includes('search-preference-chip'))
 view.rerender(<SearchIntelligence params={new URLSearchParams()} update={()=>{}} facets={null} interpretation={{...interpretation,related_concepts:['Deep learning']}}/>);assert.ok(screen.getByText('Related concepts included'))
})

test('individual subject/exclusion chip sends its server-issued remove address',()=>{
 let omitted='';render(<SearchIntelligence params={new URLSearchParams()} update={(key,value)=>{if(key==='omit')omitted=value}} facets={null} interpretation={{mode:'SMART',corrections:[],chips:[{key:'subject',label:'Genre / Subject: Fiction',remove_key:'subject@issued-value'},{key:'subject',label:'Genre / Subject: Mystery',remove_key:'subject@another-value'}]}}/>);fireEvent.click(screen.getByRole('button',{name:'Remove Genre / Subject: Fiction'}));assert.equal(omitted,'subject@issued-value');assert.ok(screen.getByRole('button',{name:'Remove Genre / Subject: Mystery'}))
})

test('successful clarification restores focus before its controls disappear',async()=>{
 login();globalThis.fetch=async()=>Response.json({interpretation:{mode:'SMART'}})
 function Resolvable(){const [done,setDone]=useState(false);return <><input id="catalogue-query" aria-label="Persistent query"/>{!done&&<SearchClarification clarification={{...clarification,candidate_choices:[{choice_id:'x',label:'Keep rating > 4'}]}} onResolved={()=>setDone(true)}/>}</>}
 render(<Resolvable/>);fireEvent.click(screen.getByRole('button',{name:'Keep rating > 4'}));await waitFor(()=>assert.ok(!screen.queryByRole('button',{name:'Keep rating > 4'}),'Resolution controls should disappear'));assert.ok(document.activeElement===screen.getByRole('textbox',{name:'Persistent query'}),'Persistent query should retain focus')
})

test('older clarification response cannot refresh a newer clarification or account',async()=>{
 login();let finish:((r:Response)=>void)|undefined,changed=false
 globalThis.fetch=async()=>new Promise(resolve=>{finish=resolve})
 const view=render(<SearchClarification clarification={{...clarification,candidate_choices:[{choice_id:'old',label:'Old choice'}]}} onResolved={()=>{changed=true}}/>);
 fireEvent.click(screen.getByRole('button',{name:'Old choice'}));await waitFor(()=>assert.ok(finish))
 view.rerender(<SearchClarification clarification={{...clarification,clarification_id:'newer',question:'Newer question',candidate_choices:[{choice_id:'new',label:'New choice'}]}} onResolved={()=>{changed=true}}/>);
 await act(async()=>finish!(Response.json({interpretation:{mode:'SMART'}})));assert.equal(changed,false);assert.ok(screen.getByText('Newer question'))
 act(()=>useAuthStore.setState({token:'new-account'}));assert.equal(changed,false)
})


