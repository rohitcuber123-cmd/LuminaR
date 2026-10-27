import type { Library, LibraryRole } from './institutions'
export type LibraryWorkspace = 'PATRON' | 'STAFF'

export function patronPath(libraryId: string, section = '') { return `/libraries/${encodeURIComponent(libraryId)}${section ? `/${section}` : ''}` }
/** Explicit Patron URLs own navigation context. This never grants membership. */
export function patronLibraryIdFromPath(pathname: string): string | null {
  return pathname.match(/^\/libraries\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\/|$)/i)?.[1] ?? null
}
export function luminarHomePath(pathname: string) {
  const libraryId = patronLibraryIdFromPath(pathname)
  return libraryId ? patronPath(libraryId) : '/'
}
export function staffPath(libraryId: string, section = '') { return `/staff/libraries/${encodeURIComponent(libraryId)}${section ? `/${section}` : ''}` }
export function libraryBookPath(libraryId:string,bookId:string,staff=false) { return workspacePath(libraryId,staff,`books/${encodeURIComponent(bookId)}`) }
export function workspacePath(libraryId: string, staff: boolean, section = '') { return staff ? staffPath(libraryId, section) : patronPath(libraryId, section) }
export function membershipLabel(library: Library) {
  const role = libraryRole(library)
  return role === 'ADMIN' ? library.membership?.is_owner ? 'Owner · Admin' : 'Admin' : role === 'LIBRARIAN' ? 'Librarian' : role === 'GENERAL_USER' ? 'Member' : 'Inactive'
}

export function libraryRole(library: Library | null | undefined): LibraryRole | null {
  return library?.membership?.status === 'ACTIVE' ? library.membership.role : null
}

export function isLibraryStaff(library: Library | null | undefined) {
  const role = libraryRole(library)
  return role === 'ADMIN' || role === 'LIBRARIAN'
}

export function libraryWorkspaceHome(library: Library | null | undefined) {
  switch (libraryRole(library)) {
    case 'ADMIN':
    case 'LIBRARIAN': return staffPath(library!.library_id)
    case 'GENERAL_USER': return patronPath(library!.library_id)
    default: return '/account/libraries'
  }
}
