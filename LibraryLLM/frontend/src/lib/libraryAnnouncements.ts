import { institutionApi } from './institutions'

export const announcementCategories = { GENERAL: 'General', EVENT: 'Event', LIBRARY_UPDATE: 'Library update', IMPORTANT_NOTICE: 'Important notice' } as const
export type AnnouncementRecipient = { user_id:number; name:string; email:string }
export type AnnouncementInput = { title: string; body: string; category: keyof typeof announcementCategories; priority: 'NORMAL'|'IMPORTANT'; linked_event_id: string|null; audience?:'ALL_ACTIVE_MEMBERS'|'SPECIFIC_MEMBER'; recipient_user_id?:number|null }
export type Announcement = AnnouncementInput & { announcement_id:string; library_id:string; status:'DRAFT'|'PUBLISHED'|'WITHDRAWN'; revision:number; created_at:string; published_at:string|null; withdrawn_at:string|null; linked_event_available:boolean; recipient?:AnnouncementRecipient|null; recipient_unavailable?:boolean; delivery?:{state:string;total?:number;cursor?:number;delivered?:number;suppressed?:number;last_error_code?:string|null} }
export type AnnouncementPage = { results:Announcement[]; total:number; has_more:boolean }
export function announcementApi(libraryId:string) {
  const base=`/libraries/${encodeURIComponent(libraryId)}`
  return {
    recipients:(query:string,signal?:AbortSignal)=>institutionApi<{library_id:string;results:AnnouncementRecipient[];has_more:boolean}>(`${base}/staff/announcement-recipients?q=${encodeURIComponent(query)}&limit=10`,'GET',undefined,signal),
    list:(staff:boolean,status:string,offset:number,signal?:AbortSignal)=>institutionApi<AnnouncementPage>(`${base}/${staff?'staff/':''}announcements?limit=20&offset=${offset}${staff&&status?'&status='+encodeURIComponent(status):''}`,'GET',undefined,signal),
    detail:(id:string,staff:boolean,signal?:AbortSignal)=>institutionApi<Announcement>(`${base}/${staff?'staff/':''}announcements/${encodeURIComponent(id)}`,'GET',undefined,signal),
    save:(data:AnnouncementInput,id:string|undefined,revision:number,requestId:string)=>institutionApi<Announcement>(`${base}/announcements${id?'/'+encodeURIComponent(id):''}`,id?'PATCH':'POST',{...data,...(id?{revision}:{request_id:requestId})}),
    action:(row:Announcement,action:'publish'|'withdraw'|'delivery/retry')=>institutionApi<Announcement>(`${base}/announcements/${encodeURIComponent(row.announcement_id)}/${action}`,'POST',action==='delivery/retry'?undefined:{revision:row.revision}),
  }
}
