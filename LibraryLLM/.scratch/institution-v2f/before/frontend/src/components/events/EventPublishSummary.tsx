import { categories, eventDate, type EventInput } from '../../lib/events'
import { EVENT_PRESETS } from '../../lib/eventPresets'
export function EventPublishSummary({ event }: { event: EventInput }) {
  const preset = EVENT_PRESETS[event.category]
  return <dl className="event-publish-summary" aria-label="Publication summary">
    <div><dt>Event Type</dt><dd>{categories[event.category]}</dd></div>
    <div><dt>Title</dt><dd>{event.title}</dd></div>
    <div><dt>{preset.startLabel}</dt><dd>{eventDate(event.start_at)}</dd></div>
    {event.end_at && <div><dt>{preset.endLabel}</dt><dd>{eventDate(event.end_at)}</dd></div>}
    <div><dt>Location</dt><dd>{event.location || 'Not specified'}</dd></div>
    <div><dt>Linked books</dt><dd>{event.related_work_ids.length}</dd></div>
  </dl>
}
