import { patronLibraryIdFromPath, patronPath } from './libraryWorkspace'

export const PATRON_RETURN_CONTEXT = 'patron_library'
export const STAFF_RETURN_CONTEXT = 'staff_library'
export type ProductRouteContext = { kind:'GLOBAL' | 'PATRON_LIBRARY' | 'STAFF_LIBRARY' | 'PLATFORM'; libraryId:string|null }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const authPaths = new Set(['/login','/signup','/staff/login','/verify-otp','/account/setup','/staff/setup','/staff-login','/verify-email','/account-setup'])
/** Route first; membership may correct patron presentation, never grant access. */
export function resolveProductContext(pathname:string,search='',membershipRole?:string|null):ProductRouteContext {
  const staff=pathname.match(/^\/staff\/libraries\/([^/]+)(?:\/|$)/)?.[1]
  if(staff && uuid.test(staff)) return {kind:'STAFF_LIBRARY',libraryId:staff}
  if(/^\/platform(?:\/|$)/.test(pathname)) return {kind:'PLATFORM',libraryId:null}
  const patron=patronLibraryIdFromPath(pathname)
  if(patron) return {kind:membershipRole==='ADMIN' || membershipRole==='LIBRARIAN' ? 'STAFF_LIBRARY':'PATRON_LIBRARY',libraryId:patron}
  if(authPaths.has(pathname)) return {kind:'GLOBAL',libraryId:null}
  const params=new URLSearchParams(search),a=params.get(STAFF_RETURN_CONTEXT),b=params.get(PATRON_RETURN_CONTEXT)
  if(params.get('workspace')==='platform' && !a && !b) return {kind:'PLATFORM',libraryId:null}
  if(a && !b && uuid.test(a)) return {kind:'STAFF_LIBRARY',libraryId:a}
  if(b && !a && uuid.test(b)) return {kind:membershipRole==='ADMIN' || membershipRole==='LIBRARIAN' ? 'STAFF_LIBRARY':'PATRON_LIBRARY',libraryId:b}
  return {kind:'GLOBAL',libraryId:null}
}
export function resolveProductHomeDestination(context:ProductRouteContext):string {
  return context.kind==='STAFF_LIBRARY' && context.libraryId ? `/staff/libraries/${context.libraryId}` :
    context.kind==='PATRON_LIBRARY' && context.libraryId ? patronPath(context.libraryId) : context.kind==='PLATFORM' ? '/platform' : '/'
}
export function productEventsPath(context:ProductRouteContext):string {
  return context.libraryId && (context.kind==='STAFF_LIBRARY' || context.kind==='PATRON_LIBRARY')
    ? `/${context.kind==='STAFF_LIBRARY'?'staff/':''}libraries/${context.libraryId}/events`
    : withProductContext('/events',context)
}
export function withProductContext(path:string,context:ProductRouteContext):string {
  if(!path.startsWith('/') || path.startsWith('//') || /^\/(staff\/libraries|platform)(?:\/|$)/.test(path) || patronLibraryIdFromPath(path.split('?')[0])) return path
  const [base,hash]=path.split('#'),[pathname,query]=base.split('?')
  if(authPaths.has(pathname)) return pathname
  const params=new URLSearchParams(query)
  params.delete(PATRON_RETURN_CONTEXT);params.delete(STAFF_RETURN_CONTEXT);params.delete('workspace')
  if(context.kind==='PATRON_LIBRARY' && context.libraryId) params.set(PATRON_RETURN_CONTEXT,context.libraryId)
  if(context.kind==='STAFF_LIBRARY' && context.libraryId) params.set(STAFF_RETURN_CONTEXT,context.libraryId)
  if(context.kind==='PLATFORM') params.set('workspace','platform')
  return `${pathname}${params.size?'?'+params:''}${hash?'#'+hash:''}`
}
/** URL presentation/return context only. Server membership guards remain authority. */
export function productLibraryId(pathname: string, search = ''): string | null {
  const routeId = patronLibraryIdFromPath(pathname)
  if (routeId) return routeId
  const directory = ['/invitations', '/libraries', '/libraries/register'].includes(pathname)
  if (!directory && !/^\/(reading-list(?:\/|$)|account\/|llm(?:\/|$)|experimental\/|events(?:\/|$)|book\/)/.test(pathname)) return null
  const id = new URLSearchParams(search).get(PATRON_RETURN_CONTEXT)
  return id && uuid.test(id) ? id : null
}
export function withPatronContext(path: string, libraryId: string | null): string {
  if (!libraryId || !uuid.test(libraryId) || path.startsWith('/staff') || path.startsWith('/platform') || patronLibraryIdFromPath(path.split('?')[0])) return path
  const [base, hash] = path.split('#'), [pathname, query] = base.split('?')
  const params = new URLSearchParams(query); params.set(PATRON_RETURN_CONTEXT, libraryId)
  return `${pathname}?${params}${hash ? '#' + hash : ''}`
}
export const productHomePath = (id: string | null) => id ? patronPath(id) : '/'
export const productCataloguePath = (id: string | null) => id ? patronPath(id, 'catalogue') : '/catalog'
export function productBookPath(workId: string, libraryId: string | null) {
  return libraryId ? patronPath(libraryId, `global-books/${encodeURIComponent(workId)}`) : `/book/${encodeURIComponent(workId)}`
}
export function productOffset(value: string | null, maximum = 100000): number {
  const number = Number(value || 0)
  return Number.isSafeInteger(number) && number >= 0 ? Math.min(maximum, number) : 0
}
