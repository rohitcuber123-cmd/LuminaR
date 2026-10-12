export interface Notice { notification_id: string; type: string; title: string; message: string; created_at: string; read_at: string | null; resolved_at?: string | null; resolution_reason?: string | null; scope?: 'GLOBAL'|'PLATFORM'|'LIBRARY'|'LEGACY_AMBIGUOUS'; library_id?:string|null; library_name?:string; audience?:'PATRON'|'STAFF'; action_route?:string|null; action_unavailable?:string|null }

/** The item's own canonical source wins; current workspace is never consulted. */
export function resolveNotificationAction(notice:Notice):string|null {
  if(notice.action_unavailable || notice.scope!=='LIBRARY' || !notice.library_id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(notice.library_id)) return null
  const pages:Record<string,string>={BORROW_REQUEST_CREATED:'circulation',RETURN_REQUEST_CREATED:'circulation?tab=return',BORROW_REQUEST_APPROVED:'my-library',BORROW_REQUEST_REJECTED:'my-library',RETURN_CONFIRMED:'my-library',RESERVATION_CREATED:'reservations',RESERVATION_READY:'reservations',RESERVATION_CANCELLED:'reservations',RESERVATION_EXPIRED:'reservations',FEE_ASSESSED:'fees',FEE_WAIVED:'fees',PAYMENT_RECORDED:'fees',FEE_ADJUSTED:'fees'}
  const page=pages[notice.type],staff=['BORROW_REQUEST_CREATED','RETURN_REQUEST_CREATED'].includes(notice.type)
  if(!page || notice.audience!==(staff?'STAFF':'PATRON')) return null
  const route=`/${staff?'staff/':''}libraries/${notice.library_id}/${page}`
  return notice.action_route===route ? route:null
}

/** Initial backlog is silent. Later unread IDs can toast once. */
export function noticeDelta(seen: Set<string>, notices: Notice[], initialized: boolean) {
  const fresh = initialized ? notices.filter(n => !n.read_at && !n.resolved_at && !seen.has(n.notification_id)) : []
  for (const n of notices) seen.add(n.notification_id)
  return fresh
}
