// Login/logout update token and user separately. Reconcile the pair after
// the storage events settle, so another tab never clears an incomplete login.
export function watchSessionStorage(reconcile: () => void) {
  let timer: ReturnType<typeof setTimeout> | undefined
  const changed = (event: StorageEvent) => {
    if (event.key !== 'luminar_token' && event.key !== 'luminar_user' && event.key !== null) return
    clearTimeout(timer)
    timer = setTimeout(reconcile, 50)
  }
  window.addEventListener('storage', changed)
  return () => { clearTimeout(timer); window.removeEventListener('storage', changed) }
}
