import { LuminarSelect } from '../components/LuminarSelect'
import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { coreRequest } from '../lib/api'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { Modal, date } from '../components/StaffUI'
import { scrollToContentAnchor } from '../lib/paginationScroll'

type Status='ACTIVE'|'SUSPENDED'|'REMOVED'
type LibrarySummary={library_id:string;name:string;slug:string;library_type:string;access_mode:string;status:string;created_at:string;updated_at:string;
  owner:{user_id:number;name:string|null;email:string|null};counts:{members:number;staff:number;local_books:number}}
type AuditEvent={event_id:string;event:string;actor_user_id:number;created_at:string;reason:string;previous_state:string;new_state:string}
type AuditPage={results:AuditEvent[];total:number;limit:number;offset:number}
type Detail={library:LibrarySummary;cutover:{circulation:string;reservations:string;fees:string};audit:AuditPage;tenant_internals_require_membership:true}
type Action='suspend'|'remove'|'restore'
const labels={suspend:'Suspend Library',remove:'Remove Library',restore:'Restore Library'}
const statusLabel=(value:string)=>value.charAt(0)+value.slice(1).toLowerCase()

export function PlatformLibrariesPage(){
  const [params,setParams]=useSearchParams(),[revision,setRevision]=useState(0)
  const limit=[5,10,20,50].includes(Number(params.get('limit'))) ? Number(params.get('limit')):20
  const rawOffset=Number(params.get('offset')||0),offset=Number.isSafeInteger(rawOffset)&&rawOffset>=0?Math.min(rawOffset,1000000):0
  const q=params.get('q')||'',status=params.get('status')||'',type=params.get('library_type')||''
  const key=params.toString()+':'+revision
  const [result,setResult]=useState<{key:string;data?:{results:LibrarySummary[];total:number;has_more:boolean};error?:string}|null>(null)
  const current=result?.key===key?result:null
  useEffect(()=>{const controller=new AbortController(),query=new URLSearchParams({limit:String(limit),offset:String(offset)})
    if(q)query.set('q',q);if(status)query.set('status',status);if(type)query.set('library_type',type)
    void coreRequest<{results:LibrarySummary[];total:number;has_more:boolean}>('/platform/libraries?'+query,{signal:controller.signal}).then(data=>{if(!controller.signal.aborted)setResult({key,data})}).catch(error=>{if(!controller.signal.aborted)setResult({key,error:error.message})})
    return()=>controller.abort()
  },[key,limit,offset,q,status,type])
  function update(name:string,value:string){const next=new URLSearchParams(params);if(value)next.set(name,value);else next.delete(name);if(name!=='offset')next.delete('offset');setParams(next)}
  return <div className="institutions platform-libraries"><PageHeading title="Libraries" description="Library identity, lifecycle and safe aggregate counts. Tenant operations require an independent library membership." />
    <form key={q} className="ui-filter-toolbar" onSubmit={event=>{event.preventDefault();update('q',String(new FormData(event.currentTarget).get('q')||'').trim())}}>
      <label>Search libraries<input type="search" name="q" defaultValue={q} maxLength={120} placeholder="Name, slug, UUID or owner" /></label><button type="submit" className="ui-button">Search</button>
      <label>Status<LuminarSelect aria-label="Library status" value={status} onChange={e=>update('status',e.target.value)}><option value="">All statuses</option>{['ACTIVE','SUSPENDED','REMOVED'].map(s=><option key={s} value={s}>{statusLabel(s)}</option>)}</LuminarSelect></label>
      <label>Type<LuminarSelect aria-label="Library type" value={type} onChange={e=>update('library_type',e.target.value)}><option value="">All types</option><option value="PUBLIC_LIBRARY">Public library</option><option value="PRIVATE_INSTITUTION">Private institution</option></LuminarSelect></label>
      <label>Per page<LuminarSelect aria-label="Libraries per page" value={limit} onChange={e=>update('limit',e.target.value)}>{[5,10,20,50].map(n=><option key={n}>{n}</option>)}</LuminarSelect></label>
    </form>
    {!current?<StatePanel kind="loading" title="Loading libraries…"/>:current.error?<StatePanel kind="error" title="Unable to load libraries" action={<button onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{current.error}</StatePanel>:<>
      <p role="status">{current.data!.total} libraries{q?' matching your search':''}</p>
      {!current.data!.results.length?<StatePanel title="No libraries found">Try another search or filter.</StatePanel>:<div className="ui-table-wrap" tabIndex={0} aria-label="Scrollable library directory"><table className="ui-table platform-library-table"><thead><tr><th>Library</th><th>Type / access</th><th>Lifecycle</th><th>Owner</th><th>Counts</th><th>Created</th><th>Action</th></tr></thead><tbody>{current.data!.results.map(row=><tr key={row.library_id}>
        <td><strong>{row.name}</strong><small>{row.library_id}</small><small>{row.slug}</small></td><td>{row.library_type==='PUBLIC_LIBRARY'?'Public library':'Private institution'}<small>{row.access_mode==='PUBLIC'?'Public':'Private code'}</small></td>
        <td><span className="ui-badge">{statusLabel(row.status)}</span></td><td>{row.owner.name||'Owner account unavailable'}<small>{row.owner.email||'—'}</small></td><td>{row.counts.local_books} books<small>{row.counts.members} members · {row.counts.staff} staff</small></td><td>{date(row.created_at)}</td>
        <td><Link className="ui-button ui-secondary" aria-label={`View ${row.name}`} to={'/platform/libraries/'+row.library_id}>View</Link></td></tr>)}</tbody></table></div>}
      <div className="ui-pagination"><button className="ui-button ui-secondary" disabled={!offset} onClick={()=>{update('offset',String(Math.max(0,offset-limit)));requestAnimationFrame(()=>scrollToContentAnchor('.ui-table-wrap, .institutions'))}}>Previous</button><span>Page {Math.floor(offset/limit)+1}</span><button className="ui-button ui-secondary" disabled={!current.data!.has_more} onClick={()=>{update('offset',String(offset+limit));requestAnimationFrame(()=>scrollToContentAnchor('.ui-table-wrap, .institutions'))}}>Next</button></div>
    </>}
  </div>
}

function LifecycleDialog({library,action,onClose,onComplete}:{library:LibrarySummary;action:Action;onClose:()=>void;onComplete:()=>void}){
  const [reason,setReason]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[idempotencyKey]=useState(()=>crypto.randomUUID())
  async function submit(event:React.FormEvent){event.preventDefault();if(!reason.trim()||busy)return;setBusy(true);setError('')
    try{await coreRequest('/platform/libraries/'+library.library_id+'/'+action,{method:'POST',body:JSON.stringify({reason:reason.trim(),expected_status:library.status,idempotency_key:idempotencyKey})});onComplete()}
    catch(error){setError(error instanceof Error?error.message:'Unable to change library lifecycle.')}finally{setBusy(false)}
  }
  return <Modal title={labels[action]} busy={busy} onClose={onClose}><form className="platform-lifecycle-form" onSubmit={submit}>
    <p><strong>{library.name}</strong></p><p>{action==='remove'?'Remove this library from discovery and deny normal patron/staff access. This is a soft removal: memberships, inventory, loans, requests, fees and documents are retained for recovery.':action==='suspend'?'Suspend normal library access and new activity. All library data is retained.':'Restore normal library access after owner, provisioning and canonical integrity checks pass. Retained data is preserved.'}</p>
    <p>Current state: {statusLabel(library.status)}. This action is recorded in the platform audit.</p>
    <label htmlFor="platform-lifecycle-reason">Reason (required)</label><textarea id="platform-lifecycle-reason" required maxLength={500} rows={3} value={reason} onChange={e=>setReason(e.target.value)} />
    {error&&<p role="alert" className="institution-error">{error}</p>}<div className="ui-actions"><button type="button" className="ui-button ui-secondary" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" className={`ui-button${action==='restore'?'':' ui-danger'}`} disabled={busy||!reason.trim()}>{busy?'Working…':labels[action]}</button></div>
  </form></Modal>
}

function PlatformAudit({libraryId,revision}:{libraryId:string;revision:number}){
  const [offset,setOffset]=useState(0),[result,setResult]=useState<{key:string;data?:AuditPage;error?:string}|null>(null),key=`${libraryId}:${revision}:${offset}`
  useEffect(()=>{const controller=new AbortController();void coreRequest<AuditPage>(`/platform/libraries/${libraryId}/audit?limit=20&offset=${offset}`,{signal:controller.signal}).then(data=>{if(!controller.signal.aborted)setResult({key,data})}).catch(error=>{if(!controller.signal.aborted)setResult({key,error:error.message})});return()=>controller.abort()},[libraryId,key,offset,revision])
  const current=result?.key===key?result:null
  return <section className="ui-card"><h2>Platform audit</h2>{!current?<StatePanel title="Loading platform audit…" kind="loading"/>:current.error?<p role="alert">{current.error}</p>:<>
    {!current.data!.results.length?<p>No platform lifecycle actions recorded.</p>:<ol className="platform-audit-list">{current.data!.results.map(event=><li key={event.event_id}><strong>{event.event}</strong><p>{event.previous_state} → {event.new_state} · {date(event.created_at)} · Actor {event.actor_user_id}</p><p>{event.reason}</p></li>)}</ol>}
    {(offset>0||current.data!.total>20)&&<div className="ui-pagination"><button className="ui-button ui-secondary" disabled={!offset} onClick={()=>{setOffset(v=>Math.max(0,v-20));requestAnimationFrame(()=>scrollToContentAnchor('.platform-audit-list, .ui-card'))}}>Previous audit events</button><span>{current.data!.total} events</span><button className="ui-button ui-secondary" disabled={offset+20>=current.data!.total} onClick={()=>{setOffset(v=>v+20);requestAnimationFrame(()=>scrollToContentAnchor('.platform-audit-list, .ui-card'))}}>Next audit events</button></div>}
  </>}</section>
}

export function PlatformLibraryDetailPage(){
  const {libraryId=''}=useParams(),[revision,setRevision]=useState(0),[action,setAction]=useState<Action|null>(null),key=`${libraryId}:${revision}`
  const [result,setResult]=useState<{key:string;data?:Detail;error?:string}|null>(null),current=result?.key===key?result:null
  useEffect(()=>{const controller=new AbortController();void coreRequest<Detail>('/platform/libraries/'+libraryId,{signal:controller.signal}).then(data=>{if(!controller.signal.aborted)setResult({key,data})}).catch(error=>{if(!controller.signal.aborted)setResult({key,error:error.message})});return()=>controller.abort()},[libraryId,key,revision])
  if(!current)return <StatePanel kind="loading" title="Loading library…"/>
  if(current.error)return <StatePanel kind="error" title="Unable to load library" action={<button onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{current.error}</StatePanel>
  const {library,cutover}=current.data!,status=library.status as Status
  const actions:Action[]=status==='ACTIVE'?['suspend','remove']:status==='SUSPENDED'?['restore','remove']:status==='REMOVED'?['restore']:[]
  return <div className="institutions platform-library-detail"><Link to="/platform/libraries">← Libraries</Link><PageHeading title={library.name} description="Platform identity and lifecycle. Tenant internals require an independent library membership." actions={<div className="ui-actions">{actions.map(a=><button key={a} className={`ui-button${a==='restore'?' ui-secondary':' ui-danger'}`} onClick={()=>setAction(a)}>{labels[a]}</button>)}</div>}/>
    <section className="ui-card"><h2>Library identity</h2><dl className="ui-details platform-library-facts">{[
      ['Library UUID',library.library_id],['Slug',library.slug],['Type',library.library_type==='PUBLIC_LIBRARY'?'Public library':'Private institution'],['Access',library.access_mode==='PUBLIC'?'Public':'Private code'],['Lifecycle',statusLabel(status)],['Owner',library.owner.name||'Unavailable'],['Owner email',library.owner.email||'—'],['Created',date(library.created_at)],['Updated',date(library.updated_at)],['Local books',library.counts.local_books],['Active members',library.counts.members],['Active staff',library.counts.staff]
    ].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></section>
    <section className="ui-card"><h2>Migration / cutover</h2><dl className="ui-details platform-library-facts">{Object.entries(cutover).map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl><p>Platform authority does not grant inventory, circulation, staff, fees or internal settings permissions.</p></section>
    <PlatformAudit key={libraryId} libraryId={libraryId} revision={revision}/>
    {action&&<LifecycleDialog library={library} action={action} onClose={()=>setAction(null)} onComplete={()=>{setAction(null);setRevision(v=>v+1)}}/>}
  </div>
}
