/** Catalogue writes invalidate every current-library read, including other tabs. */
export const CATALOGUE_CHANGED = 'luminar:catalogue-changed'
export function catalogueChanged(libraryId: string) {
  window.dispatchEvent(new window.CustomEvent(CATALOGUE_CHANGED, { detail: { library_id: libraryId } }))
  if (typeof window.BroadcastChannel !== 'undefined') {
    const channel = new window.BroadcastChannel(CATALOGUE_CHANGED)
    channel.postMessage({ library_id: libraryId }); channel.close()
  }
}
export function observeCatalogue(libraryId: string, refresh: () => void) {
  const changed = (event: Event) => { if ((event as CustomEvent).detail?.library_id === libraryId) refresh() }
  const focused = () => { if (document.visibilityState !== 'hidden') refresh() }
  const channel = typeof window.BroadcastChannel !== 'undefined' ? new window.BroadcastChannel(CATALOGUE_CHANGED) : null
  if (channel) channel.onmessage = event => { if (event.data?.library_id === libraryId) refresh() }
  window.addEventListener(CATALOGUE_CHANGED, changed)
  window.addEventListener('focus', focused); document.addEventListener('visibilitychange', focused)
  return () => { channel?.close(); window.removeEventListener(CATALOGUE_CHANGED, changed); window.removeEventListener('focus', focused); document.removeEventListener('visibilitychange', focused) }
}
