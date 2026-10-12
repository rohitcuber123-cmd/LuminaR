from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def edit(name, pairs):
    p=ROOT/name;s=p.read_text(encoding='utf8')
    for old,new in pairs:
        assert old in s,(name,old[:100])
        s=s.replace(old,new)
    p.write_text(s,encoding='utf8')


edit('frontend/src/pages/ManageEventsPage.tsx',[
    ("Link, useSearchParams", "Link, useSearchParams, useParams"),
    ("eventApi, eventDate", "eventApiFor, eventDate"),
    ("const [params, setParams]", "const {libraryId}=useParams(), api=eventApiFor(libraryId), base=libraryId ? `/staff/libraries/${libraryId}/events` : '/platform/events', browse=libraryId ? base : '/events'\n  const [reason,setReason]=useState('')\n  const [params, setParams]"),
    ("`${token}:${query}:${reload}`", "`${token}:${libraryId}:${query}:${reload}`"),
    ('eventApi.manage','api.manage'),
    ('eventApi.action(confirmation.event.event_id, confirmation.action)', "api.action(confirmation.event.event_id, confirmation.action, reason)"),
    ("to=\"/events\"", 'to={browse}'),
    ("to=\"/platform/events/new\"", "to={base+'/new'}"),
    ('PLATFORM ADMIN</span>','{libraryId ? \'STAFF WORKSPACE\' : \'PLATFORM ADMIN\'}</span>'),
    ("'/platform/events/' + event.event_id + '/edit'", "base + '/' + event.event_id + '/edit'"),
    ("'/events/' + event.event_id", "browse + '/' + event.event_id"),
    ("<div className=\"event-filters\">", "{libraryId && <div className=\"event-tabs\" role=\"group\" aria-label=\"Staff event views\">{['upcoming','draft','past','cancelled'].map(view=><button key={view} aria-pressed={view==='draft' ? params.get('status')==='DRAFT' : params.get('view')===view} onClick={()=>{const next=new URLSearchParams(params);next.delete('page');next.delete('status');next.delete('view');next.set(view==='draft'?'status':'view',view==='draft'?'DRAFT':view);setParams(next)}}>{view[0].toUpperCase()+view.slice(1)}</button>)}</div>}<div className=\"event-filters\">"),
    ("if (value) next.set(name, value);", "if(name==='status') next.delete('view'); if (value) next.set(name, value);"),
    ("onClick={() => setConfirmation({ event, action: 'cancel' })}", "onClick={() => {setReason('');setConfirmation({ event, action: 'cancel' })}}"),
    ("{error && <p role=\"alert\">{error}</p>}<div className=\"events-actions\">", "{libraryId && confirmation.action==='cancel' && <label className=\"event-cancel-reason\">Cancellation reason<input aria-label=\"Cancellation reason\" required maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} /></label>}{error && <p role=\"alert\">{error}</p>}<div className=\"events-actions\">"),
    ('disabled={busy} onClick={() => void action()}',"disabled={busy || Boolean(libraryId && confirmation.action==='cancel' && !reason.trim())} onClick={() => void action()}"),
    ('It will become visible to library users and create a new-event signal.', 'It will become visible according to this event’s visibility. Global publication also updates the global event badge.'),
])
edit('frontend/src/pages/EventEditorPage.tsx',[
    ('categories, eventApi, author','categories, eventApiFor, author'),
    ("import { useAuthStore }", "import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'\nimport { useAuthStore }"),
    ("const { eventId } = useParams()", "const { eventId, libraryId } = useParams(), api=eventApiFor(libraryId), base=libraryId ? `/staff/libraries/${libraryId}/events` : '/platform/events', library=useInstitutionStore(activeLibrary)"),
    ("`${token}:${eventId || 'new'}`", "`${token}:${libraryId}:${eventId || 'new'}`"),
    ('eventApi.detail','api.detail'),('eventApi.edit','api.edit'),('eventApi.create','api.create'),('eventApi.action','api.action'),
    ("navigate('/platform/events')",'navigate(base)'),
    ('to="/platform/events"','to={base}'),
    ('PLATFORM ADMIN</span>',"{libraryId ? 'STAFF WORKSPACE' : 'PLATFORM ADMIN'}</span>"),
    ("related_work_ids: event.related_work_ids } : empty()", "related_work_ids: event.related_work_ids, ...(libraryId ? {visibility:event.visibility || 'LIBRARY_MEMBERS'} : {}) } : {...empty(),...(libraryId ? {visibility:'LIBRARY_MEMBERS' as const}: {})}"),
    ('<section className="event-editor-section event-editor-footer">', '<section className="event-editor-section event-editor-footer">{libraryId && <label>Event visibility<select aria-label="Event visibility" value={form.visibility || \'LIBRARY_MEMBERS\'} disabled={disabled} onChange={e=>setForm({...form,visibility:e.target.value as \'LIBRARY_MEMBERS\'|\'PUBLIC\'})}><option value="LIBRARY_MEMBERS">Library members</option>{library?.library_type===\'PUBLIC_LIBRARY\' && library.access_mode===\'PUBLIC\' && <option value="PUBLIC">Public</option>}</select></label>}'),
    ('It will become visible to library users and create a new-event badge.', 'It will become visible according to this event’s visibility. Global publication also updates the global event badge.'),
])
