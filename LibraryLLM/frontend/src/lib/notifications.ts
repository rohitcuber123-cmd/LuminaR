export interface Notice { notification_id: string; type: string; title: string; message: string; created_at: string; read_at: string | null; resolved_at?: string | null; resolution_reason?: string | null }

/** Initial backlog is silent. Later unread IDs can toast once. */
export function noticeDelta(seen: Set<string>, notices: Notice[], initialized: boolean) {
  const fresh = initialized ? notices.filter(n => !n.read_at && !n.resolved_at && !seen.has(n.notification_id)) : []
  for (const n of notices) seen.add(n.notification_id)
  return fresh
}
