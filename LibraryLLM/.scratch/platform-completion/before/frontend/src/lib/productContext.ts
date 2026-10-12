import { patronLibraryIdFromPath, patronPath } from './libraryWorkspace'

export const PATRON_RETURN_CONTEXT = 'patron_library'
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
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
