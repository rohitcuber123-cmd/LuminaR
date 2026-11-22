import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { useAuthStore } from '../store/useAuthStore'
import { libraryRole } from '../lib/libraryWorkspace'
import { announcementApi, announcementCategories, type Announcement, type AnnouncementInput, type AnnouncementPage, type AnnouncementRecipient } from '../lib/libraryAnnouncements'
import { eventApiFor, type LibraryEvent } from '../lib/events'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { Modal, Pager, date } from '../components/StaffUI'
import { AnnouncementMemberPicker } from '../components/AnnouncementMemberPicker'
import { LuminarSelect } from '../components/LuminarSelect'
import './LibraryAnnouncements.css'

const empty:AnnouncementInput={title:'',body:'',category:'GENERAL',priority:'NORMAL',linked_event_id:null,audience:'ALL_ACTIVE_MEMBERS',recipient_user_id:null}

export function LibraryAnnouncementsPage({staff=false}:{staff?:boolean}) {
  const {libraryId='',announcementId}=useParams(), token=useAuthStore(s=>s.token), library=useInstitutionStore(activeLibrary), session=useInstitutionStore(s=>s.session)
  const role=libraryRole(library)
  if (!token || session!==token || library?.library_id!==libraryId || !role) return <StatePanel kind="error" title="Library access unavailable">Select a library with an active membership.</StatePanel>
  if (staff && role==='GENERAL_USER') return <StatePanel kind="error" title="Administrator access required">Open announcements through your member library workspace.</StatePanel>
  return <AnnouncementWorkspace key={`${libraryId}:${token}:${role}:${announcementId||''}:${staff}`} libraryId={libraryId} announcementId={announcementId} staff={staff&&role==='ADMIN'} staffWorkspace={staff} token={token} />
}

function AnnouncementWorkspace({libraryId,announcementId,staff,staffWorkspace,token}:{libraryId:string;announcementId?:string;staff:boolean;staffWorkspace:boolean;token:string}) {
  const api=useMemo(()=>announcementApi(libraryId),[libraryId])
  const [status,setStatus]=useState(''),[page,setPage]=useState(0),[revision,setRevision]=useState(0)
  const [data,setData]=useState<AnnouncementPage|null>(null),[detail,setDetail]=useState<Announcement|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
  const [loading,setLoading]=useState(true)
  const [editor,setEditor]=useState<{row?:Announcement;data:AnnouncementInput;requestId:string;recipient?:AnnouncementRecipient|null}|null>(null)
  const [preview,setPreview]=useState<Announcement|null>(null),[confirm,setConfirm]=useState<{row:Announcement;action:'publish'|'withdraw'}|null>(null)
  const [events,setEvents]=useState<LibraryEvent[]>([]),[eventsError,setEventsError]=useState('')
  const editing=editor!==null
  const current=()=>useAuthStore.getState().token===token && useInstitutionStore.getState().activeId===libraryId
  const base=`/${staffWorkspace?'staff/':''}libraries/${libraryId}/announcements`
  useEffect(()=>{
    const controller=new AbortController()
    const accept=(row:Announcement)=>{if(row.library_id!==libraryId||!staff&&(row.status!=='PUBLISHED'||row.audience==='SPECIFIC_MEMBER'&&row.recipient_user_id!==useAuthStore.getState().user?.user_id))throw new Error('Announcement unavailable in this library context.');return row}
    const load=announcementId?api.detail(announcementId,staff,controller.signal).then(row=>{if(!controller.signal.aborted)setDetail(accept(row))}):api.list(staff,status,page*20,controller.signal).then(result=>{if(!controller.signal.aborted)setData({...result,results:result.results.map(accept)})})
    void load.catch(reason=>{if(!controller.signal.aborted){setData(null);setDetail(null);setError(reason instanceof Error?reason.message:'Unable to load announcements.')}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return ()=>controller.abort()
  },[api,libraryId,announcementId,staff,status,page,revision])
  useEffect(()=>{
    if(!editing)return
    const controller=new AbortController()
    void eventApiFor(libraryId).manage('status=PUBLISHED&page_size=50',controller.signal).then(result=>{if(!controller.signal.aborted){setEvents(result.events);setEventsError('')}}).catch(()=>{if(!controller.signal.aborted)setEventsError('Linked events could not be loaded. You can retry by reopening the draft.')})
    return ()=>controller.abort()
  },[editing,libraryId])
  useEffect(()=>{const refresh=()=>{setLoading(true);setError('');setRevision(v=>v+1)};window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh)},[])
  async function save() {
    if(!editor)return
    if(editor.data.audience==='SPECIFIC_MEMBER'&&(!editor.data.recipient_user_id||!editor.recipient)){setError('Select a member before saving this private announcement.');return}
    setBusy(true);setError('')
    try {await api.save(editor.data,editor.row?.announcement_id,editor.row?.revision||0,editor.requestId);if(current()){setEditor(null);setData(null);setDetail(null);setLoading(true);setMessage('Draft saved.');setRevision(v=>v+1)}}
    catch(reason){if(current())setError(reason instanceof Error?reason.message:'Unable to save draft. Retry with the same request or reload a changed draft.')}
    finally{if(current())setBusy(false)}
  }
  async function action(row:Announcement,operation:'publish'|'withdraw'|'delivery/retry') {
    setBusy(true);setError('')
    try {const result=await api.action(row,operation);if(current()){setConfirm(null);setPreview(null);setData(null);setDetail(null);setLoading(true);setMessage(operation==='withdraw'?'Announcement withdrawn.':`Published. Notification delivery ${result.delivery?.state==='COMPLETE'?'complete':'pending'} (${result.delivery?.cursor||0}/${result.delivery?.total||0} processed).`);setRevision(v=>v+1)}}
    catch(reason){if(current())setError(reason instanceof Error?reason.message:'Unable to update announcement. Reload to check the authoritative outcome before retrying.')}
    finally{if(current())setBusy(false)}
  }
  function audienceLabel(row:Announcement){return row.audience==='SPECIFIC_MEMBER'?(staff?(row.recipient?`Selected member: ${row.recipient.name} (${row.recipient.email})`:`Selected account ${row.recipient_user_id} is currently unavailable.${row.status==='DRAFT'?' Edit the draft to select an eligible member.':''}`):'Private message for you'):'All active members'}
  function show(row:Announcement){return <><p className="announcement-recipient">{audienceLabel(row)}</p><p><span className="ui-badge">{announcementCategories[row.category]}</span> <span className="ui-badge">{row.priority==='IMPORTANT'?'Important':'Normal'}</span> {staff&&<span className="ui-badge">{row.status}</span>}</p><p className="announcement-body">{row.body}</p>{row.linked_event_id&&(row.linked_event_available?<Link className="ui-button ui-secondary" to={`/${staffWorkspace?'staff/':''}libraries/${libraryId}/events/${row.linked_event_id}`}>Open linked event</Link>:<p>Linked event unavailable.</p>)}{row.published_at&&<p className="announcement-muted">Published {date(row.published_at)}</p>}{staff&&row.delivery?.total!==undefined&&<p role="status">Notification delivery: {row.delivery.state.toLowerCase()} · {row.delivery.cursor}/{row.delivery.total} processed · {row.delivery.delivered} delivered · {row.delivery.suppressed} suppressed{row.delivery.last_error_code&&' · Delivery failed; retry is safe.'}</p>}</>}
  return <div className="institutions announcements" aria-busy={loading}><PageHeading title="Announcements" description={staff?'Prepare drafts and publish messages to your library members.':'Messages from your library. Published announcements follow your current membership.'} />
    <div className="ui-actions">{announcementId&&<Link className="ui-button ui-secondary" to={base}>Back to announcements</Link>}<Link className="ui-button ui-secondary" to={`/${staffWorkspace?'staff/':''}libraries/${libraryId}/events`}>Events</Link>{staff&&<button className="ui-button" onClick={()=>setEditor({data:{...empty},requestId:crypto.randomUUID()})}>Create announcement</button>}</div>
    {message&&<p role="status">{message}</p>}{error&&<StatePanel kind="error" title="Announcement request failed" action={<button onClick={()=>{setEditor(null);setConfirm(null);setLoading(true);setError('');setRevision(v=>v+1)}}>Reload announcements</button>}>{error}</StatePanel>}
    {!announcementId&&staff&&<label className="announcement-filter">Status<LuminarSelect aria-label="Announcement status" value={status} onChange={e=>{setData(null);setLoading(true);setError('');setStatus(e.target.value);setPage(0)}}><option value="">All statuses</option><option value="DRAFT">Draft</option><option value="PUBLISHED">Published</option><option value="WITHDRAWN">Withdrawn</option></LuminarSelect></label>}
    {announcementId?detail?<article className="ui-card"><h2>{detail.title}</h2>{show(detail)}</article>:!error&&<StatePanel kind="loading" title="Loading announcement…" />:!data?!error&&<StatePanel kind="loading" title="Loading announcements…" />:<><div className="announcement-list">{data.results.length?data.results.map(row=><article className="ui-card" key={row.announcement_id}><h2>{staff?row.title:<Link to={`${base}/${row.announcement_id}`}>{row.title}</Link>}</h2>{show(row)}{staff&&<div className="ui-actions"><button className="ui-button ui-secondary" onClick={()=>setPreview(row)}>Preview</button>{row.status==='DRAFT'&&<><button className="ui-button ui-secondary" onClick={()=>setEditor({row,data:{title:row.title,body:row.body,category:row.category,priority:row.priority,linked_event_id:row.linked_event_id,audience:row.audience||'ALL_ACTIVE_MEMBERS',recipient_user_id:row.recipient_user_id||null},recipient:row.recipient,requestId:crypto.randomUUID()})}>Edit draft</button><button disabled={row.audience==='SPECIFIC_MEMBER'&&(!row.recipient||row.recipient_unavailable)} className="ui-button" onClick={()=>setConfirm({row,action:'publish'})}>Publish</button></>}{row.status==='PUBLISHED'&&<><button className="ui-button ui-secondary" onClick={()=>setConfirm({row,action:'withdraw'})}>Withdraw</button>{['PENDING','FAILED'].includes(row.delivery?.state||'')&&<button disabled={busy} className="ui-button ui-secondary" onClick={()=>void action(row,'delivery/retry')}>Retry delivery</button>}</>}</div>}</article>):<StatePanel title="No announcements">{staff?'Create a draft to communicate with your members.':'Your library has no published announcements yet.'}</StatePanel>}</div><Pager page={page} count={data.total} onChange={next=>{setData(null);setLoading(true);setError('');setPage(next)}} /></>}
    {editor&&<Modal title={editor.row?'Edit draft':'Create announcement'} busy={busy} onClose={()=>setEditor(null)}><form className="announcement-form" onSubmit={e=>{e.preventDefault();void save()}}>
      {error&&<p role="alert">{error}</p>}<label>Title<input required minLength={3} maxLength={140} value={editor.data.title} onChange={e=>setEditor({...editor,data:{...editor.data,title:e.target.value}})} /></label>
      <label>Message<textarea required maxLength={5000} rows={8} value={editor.data.body} onChange={e=>setEditor({...editor,data:{...editor.data,body:e.target.value}})} /></label>
      <label>Recipient scope<LuminarSelect aria-label="Recipient scope" value={editor.data.audience||'ALL_ACTIVE_MEMBERS'} onChange={e=>setEditor({...editor,recipient:null,data:{...editor.data,audience:e.target.value as AnnouncementInput['audience'],recipient_user_id:null}})}><option value="ALL_ACTIVE_MEMBERS">All active members</option><option value="SPECIFIC_MEMBER">Specific member</option></LuminarSelect></label>
      {editor.data.audience==='SPECIFIC_MEMBER'&&<><AnnouncementMemberPicker libraryId={libraryId} token={token} value={editor.recipient||null} onChange={recipient=>setEditor(previous=>previous?{...previous,recipient,data:{...previous.data,recipient_user_id:recipient?.user_id||null}}:null)} />{!editor.recipient&&<p role="alert">Select a member before saving this private announcement.</p>}</>}
      <label>Category<LuminarSelect aria-label="Category" value={editor.data.category} onChange={e=>setEditor({...editor,data:{...editor.data,category:e.target.value as AnnouncementInput['category']}})}>{Object.entries(announcementCategories).map(([key,label])=><option key={key} value={key}>{label}</option>)}</LuminarSelect></label>
      <label>Priority<LuminarSelect aria-label="Priority" value={editor.data.priority} onChange={e=>setEditor({...editor,data:{...editor.data,priority:e.target.value as AnnouncementInput['priority']}})}><option value="NORMAL">Normal</option><option value="IMPORTANT">Important</option></LuminarSelect></label>
      <label>Linked event (optional)<LuminarSelect aria-label="Linked event (optional)" value={editor.data.linked_event_id||''} onChange={e=>setEditor({...editor,data:{...editor.data,linked_event_id:e.target.value||null}})}><option value="">No linked event</option>{events.map(event=><option value={event.event_id} key={event.event_id}>{event.title}</option>)}{editor.data.linked_event_id&&!events.some(e=>e.event_id===editor.data.linked_event_id)&&<option value={editor.data.linked_event_id}>Existing linked event (not in this page)</option>}</LuminarSelect></label>
      {eventsError&&<p role="status">{eventsError}</p>}<p>Plain text only. Do not include credentials or private member information.</p><div className="ui-actions"><button className="ui-button" disabled={busy||editor.data.audience==='SPECIFIC_MEMBER'&&!editor.recipient||editor.data.title.trim().length<3||!editor.data.body.trim()||/[<>]/.test(editor.data.title+editor.data.body)}>{busy?'Saving…':'Save draft'}</button><button type="button" className="ui-button ui-secondary" disabled={busy} onClick={()=>setEditor(null)}>Cancel</button></div>
    </form></Modal>}
    {preview&&<Modal title="Announcement preview" onClose={()=>setPreview(null)}><h2>{preview.title}</h2>{show(preview)}</Modal>}
    {confirm&&<Modal title={confirm.action==='publish'?'Publish announcement?':'Withdraw announcement?'} busy={busy} onClose={()=>setConfirm(null)}><h2>{confirm.row.title}</h2><p className="announcement-recipient">{audienceLabel(confirm.row)}</p><p>{confirm.action==='publish'?(confirm.row.audience==='SPECIFIC_MEMBER'?'Only the selected eligible member will receive an in-app notification. Published content cannot be edited. Delivery completion is reported separately.':'Current eligible members will receive an in-app notification. Published content cannot be edited. Delivery completion is reported separately.'):'Members will no longer be able to open this announcement. Its publication history will remain.'}</p>{error&&<p role="alert">{error}</p>}<div className="ui-actions"><button className="ui-button" disabled={busy} onClick={()=>void action(confirm.row,confirm.action)}>{busy?'Please wait…':confirm.action==='publish'?'Publish announcement':'Withdraw announcement'}</button><button className="ui-button ui-secondary" disabled={busy} onClick={()=>setConfirm(null)}>Cancel</button></div></Modal>}
  </div>
}
