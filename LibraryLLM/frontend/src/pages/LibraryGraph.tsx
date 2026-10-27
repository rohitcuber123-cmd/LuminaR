import {useEffect,useState} from 'react'
import {Link,useParams} from 'react-router-dom'
import {institutionApi} from '../lib/institutions'
import {MetadataGraphCanvas} from '../components/MetadataGraphCanvas'
import {PageHeading,StatePanel} from '../components/WorkspaceUI'
import {libraryBookPath} from '../lib/libraryWorkspace'
import type {KGNode} from '../lib/knowledgeGraph'
import {useAuthStore} from '../store/useAuthStore'
import {useProductContext} from '../hooks/useProductContext'
type Graph={library_id:string;source:'TENANT_KG';status:string;generation_id?:string;notice?:string;requestKey?:string;nodes:Array<{id:string;type:string;label:string;library_book_id?:string}>;edges:Array<{source:string;target:string;relation:string}>}
export function LibraryGraphPage({staff=false}:{staff?:boolean}) {
  const {libraryId=''}=useParams();const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[data,setData]=useState<Graph|null>(null),[selection,setSelection]=useState<{key:string;node:KGNode}|null>(null),[failure,setFailure]=useState({key:'',message:''})
  const token=useAuthStore(state=>state.token)
  const productContext=useProductContext()
  const requestKey=`${token}:${libraryId}:${staff}:${search}`
  const selected=selection?.key===requestKey?selection.node:null
  const setSelected=(node:KGNode)=>setSelection({key:requestKey,node})
  useEffect(()=>{const controller=new AbortController();void institutionApi<Graph>(`/libraries/${libraryId}/intelligence/graph?staff=${staff}&query=${encodeURIComponent(search)}`,'GET',undefined,controller.signal).then(result=>{if(!controller.signal.aborted){if(result.library_id!==libraryId||result.source!=='TENANT_KG')throw new Error('Library graph context changed.');setData({...result,requestKey});setFailure({key:requestKey,message:''})}}).catch(reason=>{if(!controller.signal.aborted)setFailure({key:requestKey,message:reason.message})});return()=>controller.abort()},[libraryId,staff,search,requestKey])
  const current=data?.requestKey===requestKey?data:null
  const error=failure.key===requestKey?failure.message:''
  const nodes=current?.nodes.map((n,index)=>({id:n.id,kind:n.type.toLowerCase(),label:n.label,seed:n.type==='Book'&&index===current.nodes.findIndex(x=>x.type==='Book')}))||[]
  const book=current?.nodes.find(n=>n.id===selected?.id&&n.type==='Book')
  return <div className="global-page institutions"><PageHeading title="Library Knowledge Graph" description="Connections from this library’s catalogue metadata. Document contents and member activity are excluded."/><form className="ui-filter-toolbar" onSubmit={event=>{event.preventDefault();setSearch(query)}}><label>Find a book<input value={query} onChange={event=>setQuery(event.target.value)} maxLength={150}/></label><button>Search graph</button></form>{error?<StatePanel kind="error" title="Unable to load this library graph">{error}</StatePanel>:!current?<StatePanel kind="loading" title="Loading library graph…"/>:current.status!=='READY'?<StatePanel title={`Library graph: ${current.status.replaceAll('_',' ').toLowerCase()}`}>{current.notice}</StatePanel>:<><p className="ui-result-count" data-graph-source="TENANT_KG">{current.nodes.length} nodes · {current.edges.length} relationships · Library {libraryId}</p><div className="ui-card max-w-full overflow-auto" role="region" aria-label="Library graph map" tabIndex={0}><MetadataGraphCanvas nodes={nodes} edges={current.edges.map(e=>({...e,predicate:e.relation}))} selected={selected} onSelect={setSelected}/></div>{selected&&<aside className="ui-card" aria-label="Graph node details"><h2>{selected.label}</h2>{book?.library_book_id&&<Link to={libraryBookPath(libraryId,book.library_book_id,staff)}>Open book details</Link>}</aside>}</>}<p className="mt-6"><Link to={productContext.personalPath('/experimental/kg')}>Explore Global Graph Lab</Link></p></div>
}
