import type { DisplayBook } from './libraryCatalogue'
import type { Membership } from './institutions'
import { libraryBookPath } from './libraryWorkspace'
import { assetPath } from './libraryAssets'

/** Backend format flags describe current-user-accessible READY resources.
 * These hints never authorize bytes: metadata/viewer endpoints recheck access.
 */
export function resolveLibraryBookCapabilities(book: DisplayBook, membership?: Membership | null) {
  const owned=book.source==='LIBRARY' && book.owned_by_current_library && !!book.library_book_id
  const hasPhysical=owned && (book.has_physical ?? (book.book_format ? ['PHYSICAL_ONLY','PHYSICAL_AND_DIGITAL'].includes(book.book_format) : book.requestable_count != null))
  const hasOnline=owned && book.has_online===true
  const patron=membership?.library_id===book.library_id && membership.status==='ACTIVE' && membership.role==='GENERAL_USER'
  const canReadOnline=patron && hasOnline
  const readPath=canReadOnline ? book.online_asset_id ? libraryReadOnlinePath(book.library_id,book.library_book_id!,book.online_asset_id) :
    libraryBookPath(book.library_id,book.library_book_id!)+'#digital-resources' : null
  const knowMorePath=canReadOnline ? book.online_asset_id ? libraryKnowMorePath(book.library_id,book.library_book_id!,book.online_asset_id) :
    libraryBookPath(book.library_id,book.library_book_id!)+'#digital-resources' : null
  return {hasPhysical,hasOnline,canReadOnline,readPath,knowMorePath,
    canRequestPhysical:patron && hasPhysical && book.actions.request && book.circulation_status==='CIRCULATING' && (book.requestable_count || 0)>0,
    canJoinWaitlist:patron && hasPhysical && book.actions.reserve && book.circulation_status==='CIRCULATING' && book.requestable_count===0,
    format:hasPhysical && hasOnline ? 'Physical + Online' : hasOnline ? 'Online' : hasPhysical ? 'Physical' : null}
}
export function libraryReadOnlinePath(libraryId:string,bookId:string,assetId:string,staff=false) {
  const params=new URLSearchParams({book:bookId,open:'1'})
  return assetPath(libraryId,staff,assetId)+'?'+params
}
export function libraryKnowMorePath(libraryId:string,bookId:string,assetId:string,staff=false) {
  const params=new URLSearchParams({library_id:libraryId,library_book:bookId,library_asset:assetId,
    [staff ? 'staff_library' : 'patron_library']:libraryId})
  return '/llm?'+params
}
