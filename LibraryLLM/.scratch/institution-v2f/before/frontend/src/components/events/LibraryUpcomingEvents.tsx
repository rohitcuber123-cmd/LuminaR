import {useEffect,useState} from 'react'
import {Link} from 'react-router-dom'
import {useAuthStore} from '../../store/useAuthStore'
import {eventApiFor,type LibraryEvent} from '../../lib/events'
import {EventCard} from './EventUI'
import '../../pages/Events.css'

/** Optional, bounded home section. Empty/error states leave the accepted home intact. */
export function LibraryUpcomingEvents({libraryId}:{libraryId:string}) {
  const token=useAuthStore(s=>s.token)
  const [result,setResult]=useState<{key:string;events:LibraryEvent[]}|null>(null)
  const key=`${token}:${libraryId}`
  useEffect(()=>{const controller=new AbortController();void eventApiFor(libraryId).list('view=upcoming&page_size=3',controller.signal).then(data=>{if(!controller.signal.aborted && Array.isArray(data.events)) setResult({key,events:data.events})}).catch(()=>{});return()=>controller.abort()},[key,libraryId])
  if(result?.key!==key || !result.events.length)return null
  return <section className="events-shell" aria-label="Upcoming library events"><header className="events-heading"><h2>Upcoming Events</h2><Link className="event-link" to={`/libraries/${libraryId}/events`}>All library events</Link></header><div className="event-grid">{result.events.map(event=><EventCard key={event.event_id} event={event}/>)}</div></section>
}
