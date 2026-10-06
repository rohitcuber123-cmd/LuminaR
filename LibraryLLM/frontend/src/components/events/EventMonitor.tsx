import { useEffect } from 'react'
import { useAuthStore } from '../../store/useAuthStore'
import { useEventStore } from '../../store/useEventStore'
import { eventApi, eventDelta, EVENTS_CHANGED } from '../../lib/events'
import { showToast } from '../Toast'

// One app-level Events subscription. NotificationCenter keeps its existing
// independent inbox policy/timer; there was no shared scheduler to duplicate.
export function EventMonitor() {
  const token = useAuthStore(s => s.token)
  const active = useAuthStore(s => s.isAuthenticated)
  useEffect(() => {
    if (!token || !active) return
    let alive = true, inFlight = false, pending = false, initialized = false
    const observed = new Set<string>()
    const controller = new AbortController()
    const load = async () => {
      if (!alive) return
      if (inFlight) { pending = true; return }
      inFlight = true
      const revision = useEventStore.getState().revision
      try {
        const data = await eventApi.unseen(controller.signal)
        if (!alive || useAuthStore.getState().token !== token) return
        // A page may acknowledge events while this older poll is in flight.
        // Refresh rather than restore a count from before that acknowledgement.
        if (useEventStore.getState().revision !== revision) { pending = true; return }
        const fresh = eventDelta(observed, data, initialized)
        initialized = true
        useEventStore.getState().set(token, data.count)
        if (fresh) showToast(fresh.title, 'info', { title: 'New library event', href: '/events/' + fresh.event_id, actionLabel: 'View Event', durationMs: 7000, scope: token })
      } catch { /* The Events page provides retry; header/inbox remain usable. */ }
      finally { inFlight = false; if (pending && alive) { pending = false; void load() } }
    }
    const focused = () => { if (document.visibilityState !== 'hidden') void load() }
    void load()
    const timer = setInterval(focused, 60000)
    window.addEventListener('focus', focused); document.addEventListener('visibilitychange', focused)
    window.addEventListener(EVENTS_CHANGED, focused)
    return () => { alive = false; controller.abort(); clearInterval(timer); window.removeEventListener('focus', focused); document.removeEventListener('visibilitychange', focused); window.removeEventListener(EVENTS_CHANGED, focused) }
  }, [token, active])
  return null
}
