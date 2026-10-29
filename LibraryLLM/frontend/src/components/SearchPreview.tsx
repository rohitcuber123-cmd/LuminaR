import {useEffect,useEffectEvent,useLayoutEffect,useRef,useState,type FormEvent} from 'react'
import {Link,useSearchParams} from 'react-router-dom'
import {request,ApiError,type SearchResult} from '../lib/api'
import type {DisplayBook} from '../lib/libraryCatalogue'
import {searchBookPresentation} from '../lib/bookPresentation'
import {useAuthStore} from '../store/useAuthStore'
import type {SearchMode} from '../lib/searchNlu'
import type {PreviewResponse,PreviewOperation} from '../lib/searchPreview'
import {CatalogueSurface,CatalogueGrid} from './CatalogueSurface'
import {BookCard} from './BookCard'
import {LuminarSelect} from './LuminarSelect'
import {StatePanel} from './WorkspaceUI'
import '../styles/search-preview.css'

function IssuedOperation({operation,busy,apply}:{operation:PreviewOperation;busy:boolean;apply:(op:PreviewOperation,value?:string)=>void}) {
  const [value,setValue]=useState('')
  function submit(event:FormEvent){event.preventDefault();apply(operation,value)}
  if(!operation.input_type)return <button type="button" disabled={busy} className="ui-button ui-secondary" onClick={()=>apply(operation)}>{operation.label}</button>
  return <form className="search-preview-operation" onSubmit={submit}>
    <label>{operation.label}{operation.input_type==='select'?<LuminarSelect aria-label={operation.label} value={value} disabled={busy} onChange={e=>setValue(e.target.value)}><option value="">Choose…</option>{operation.options?.map(v=><option key={v} value={v}>{v}</option>)}</LuminarSelect>:
      <input aria-label={operation.label} type={operation.input_type} min={operation.field==='rating'?0:undefined} max={operation.field==='rating'?5:undefined} step="any" maxLength={100} value={value} disabled={busy} onChange={e=>setValue(e.target.value)} />}</label>
    <button className="ui-button ui-secondary" disabled={busy||!value.trim()}>Apply</button>
  </form>
}

/** Key by login/library/workspace at the parent. No result or state cache. */
export function SearchPreview({libraryId,staff=false,initialQuery='',initialMode='SMART',exitPath='/search'}:{libraryId?:string;staff?:boolean;initialQuery?:string;initialMode?:SearchMode;exitPath?:string}) {
  const [params,setParams]=useSearchParams()
  const token=useAuthStore(s=>s.token),[query,setQuery]=useState(initialQuery),[mode,setMode]=useState<SearchMode>(initialMode)
  const [data,setData]=useState<PreviewResponse|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const [books,setBooks]=useState<DisplayBook[]>([]),controller=useRef<AbortController|null>(null),sequence=useRef(0),input=useRef<HTMLTextAreaElement>(null)
  const state=useRef<PreviewResponse['preview']|null>(null)
  const inFlight=useRef(false)
  const binding=JSON.stringify([token,libraryId,staff]),live=useRef(binding)
  useLayoutEffect(()=>{live.current=binding},[binding])
  const length=Array.from(query).length,tooLong=length>500
  useEffect(()=>()=>{sequence.current++;controller.current?.abort();inFlight.current=false},[])
  async function send(op?:PreviewOperation,value?:string,offset=0,initial=false) {
    if(tooLong||inFlight.current||!query.trim()&&!op)return
    inFlight.current=true
    const ticket=++sequence.current,scope=live.current
    controller.current?.abort();const currentController=new AbortController();controller.current=currentController
    const timeout=setTimeout(()=>currentController.abort(new DOMException('Search timed out.','TimeoutError')),30000)
    setBusy(true);setError('');setBooks([])
    const previous=initial?null:state.current
    try {
      const response=await request<PreviewResponse>('/search-api/query/preview',{method:'POST',signal:currentController.signal,body:JSON.stringify({
        query:op?previous?.accepted_query:query,mode,library_id:libraryId,staff,offset,limit:10,
        ...(previous&&previous.mode===mode?{state_id:previous.state_id,version:previous.accepted_plan_version}:{}),
        ...(op?{operation_id:op.operation_id,value}:{}),
      })})
      if(sequence.current!==ticket||live.current!==scope)return
      if(libraryId&&(response.source?.library_id!==libraryId||response.source.catalogue_source!=='LIBRARY_LOCAL'||response.results.some(b=>b.library_id!==libraryId||b.source!=='LIBRARY')))
        throw new Error('The library context changed. Retry in the current library.')
      state.current=response.preview;setData(response);setQuery(response.preview.accepted_query)
      const next=new URLSearchParams(params);next.set(libraryId?'search':'q',response.preview.accepted_query);next.set('mode',mode);next.set('search_preview','1');setParams(next,{replace:true})
      setBooks(libraryId?response.results:response.results.map(book=>searchBookPresentation(book as unknown as SearchResult)))
      if(op)input.current?.focus()
    } catch(cause) {
      if(sequence.current===ticket&&live.current===scope){setData(null);setError(cause instanceof ApiError&&cause.status===503?'Search is temporarily unavailable. Your query is unchanged; retry.':cause instanceof Error?cause.message:'Search is temporarily unavailable.');}
    } finally {clearTimeout(timeout);if(sequence.current===ticket&&live.current===scope){inFlight.current=false;setBusy(false)}}
  }
  const initialSearch=useEffectEvent(()=>{if(initialQuery.trim())void send(undefined,undefined,0,true)})
  useEffect(()=>{const timer=setTimeout(()=>initialSearch(),0);return()=>clearTimeout(timer)},[]) // StrictMode rehearsal cancels before sending
  function changeMode(value:SearchMode){controller.current?.abort();sequence.current++;inFlight.current=false;state.current=null;setData(null);setBooks([]);setBusy(false);setMode(value);setError('')}
  function submit(event:FormEvent){event.preventDefault();void send()}
  const accepted=data?.preview,executable=accepted&&['EXECUTABLE','EXECUTABLE_WITH_NOTICE'].includes(accepted.decision)
  const operations=accepted?.operations || [],resolutions=operations.filter(o=>o.kind==='complete'||o.kind.startsWith('correction_'))
  const removals=operations.filter(o=>o.kind==='remove'),refinements=operations.filter(o=>o.kind==='add')
  const chips=executable?data?.interpretation.chips.filter(c=>c.key!=='topic')||[]:[]
  return <div className="search-preview"><CatalogueSurface title="Search preview" description={libraryId?'Search this library’s collection.':'Search the global catalogue.'}
    notice={<p className="search-preview-notice">Preview is enabled for your account. <Link to={exitPath}>Use standard search</Link></p>}
    search={<form className="search-preview-query" onSubmit={submit} aria-busy={busy}>
      <label>Search mode<LuminarSelect aria-label="Search mode" value={mode} disabled={busy} onChange={e=>changeMode(e.target.value as SearchMode)}><option value="SMART">Smart</option><option value="EXACT">Exact</option><option value="TITLE_AUTHOR">Title / Author</option><option value="GENRE_SUBJECT">Genre / Subject</option></LuminarSelect></label>
      <label className="search-preview-input">Search query<textarea ref={input} id="catalogue-preview-query" aria-describedby="search-preview-length" aria-invalid={tooLong} readOnly={busy} rows={3} value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!e.nativeEvent.isComposing){e.preventDefault();void send()}}} /></label>
      <span id="search-preview-length" role={tooLong?'alert':undefined}>{length}/500 characters{tooLong?' — shorten your query to search.':''}</span>
      <button className="ui-button" disabled={busy||tooLong||!query.trim()}>{busy?'Searching…':'Search'}</button>
    </form>}
    filters={<>
      {accepted&&<section aria-label="Accepted search" className="search-preview-state"><p><strong>Accepted query:</strong> {accepted.accepted_query}</p>
        {accepted.original_query!==accepted.accepted_query&&<details><summary>Original wording</summary><p>{accepted.original_query}</p></details>}
        {chips.length>0&&<div role="group" aria-label="Enforced filters" className="search-query-chips">{chips.map((chip,i)=><span className="search-query-chip" key={i}>{chip.label}</span>)}</div>}
        {accepted.advisory&&<p className="search-preview-advisory">Preference: {accepted.advisory}</p>}
        {!executable&&<p role="status">{accepted.message||'Clarify the required filter, or edit the query.'}</p>}
        {resolutions.length>0&&<div className="search-preview-operations" aria-label="Clarify or correct your search">{resolutions.map(op=><IssuedOperation key={op.operation_id} operation={op} busy={busy} apply={(operation,value)=>void send(operation,value)}/>)}</div>}
        {(refinements.length>0||removals.length>0)&&<details><summary>Refine this search</summary><div className="search-preview-operations">{[...removals,...refinements].map(op=><IssuedOperation key={op.operation_id} operation={op} busy={busy} apply={(operation,value)=>void send(operation,value)}/>)}</div></details>}
      </section>}
      {data?.coverage&&<p className="search-preview-coverage">{data.coverage.notice}</p>}
    </>}
    loading={busy} error={error} retry={()=>{state.current=null;void send(undefined,undefined,0,true)}}
    count={executable&&books.length?`${books.length} results on this page · ranked search window`:undefined}
    empty={!busy&&!error&&!books.length&&<StatePanel title={accepted&&!executable?'Refine your search to continue':accepted?'No books match these filters':'Describe the books you want'}>Use Smart for a topic and supported filters, or Exact for the existing title and identifier lookup.</StatePanel>}
    pagination={executable&&<div className="ui-actions" aria-label="Search pagination"><button className="ui-button ui-secondary" disabled={busy||query!==accepted.accepted_query||data.offset===0} onClick={()=>void send(undefined,undefined,Math.max(0,data.offset-data.limit))}>Previous</button><button className="ui-button ui-secondary" disabled={busy||query!==accepted.accepted_query||!data.has_more} onClick={()=>void send(undefined,undefined,data.offset+data.limit)}>Next results</button></div>}>
    <CatalogueGrid>{books.map(book=><BookCard key={book.display_id} book={book}/>)}</CatalogueGrid>
  </CatalogueSurface></div>
}
