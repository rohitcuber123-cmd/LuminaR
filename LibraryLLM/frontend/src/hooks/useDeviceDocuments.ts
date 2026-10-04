import { useCallback, useEffect, useRef, useState } from 'react'
import { getToken } from '../lib/api'
import { localDocumentCache } from '../lib/localDocumentCache'
import { documentCacheScope, listDeviceCopies, keepDocumentOnDevice, restoreDeviceCopy, type DeviceCopy } from '../lib/documentCacheApi'

export function useDeviceDocuments(token: string | null) {
  const [enabled, setEnabled] = useState(false), [owner, setOwner] = useState('')
  const [copies, setCopies] = useState<DeviceCopy[]>([]), [notice, setNotice] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [saved, setSaved] = useState<Record<string, string>>({})
  const revision = useRef(0)
  const refresh = useCallback(async (scope: string) => {
    const version = revision.current
    const items = await listDeviceCopies(scope)
    if (version === revision.current && token === getToken()) setCopies(items)
  }, [token])
  useEffect(() => {
    const version = ++revision.current
    let cancelled = false
    // This effect discards private state when the authenticated session changes.
    // eslint-disable-next-line react/set-state-in-effect
    setEnabled(false); setOwner(''); setCopies([]); setSaved({}); setNotice(''); setBusy(null)
    if (token) void documentCacheScope().then(scope => {
      if (cancelled || version !== revision.current || token !== getToken()) return
      setEnabled(scope.enabled && localDocumentCache.isSupported())
      if (scope.owner_scope_id) { setOwner(scope.owner_scope_id); void refresh(scope.owner_scope_id).catch(() => setNotice('Device copies could not be loaded.')) }
    }).catch(() => { /* Upload remains usable when optional caching is unavailable. */ })
    return () => { cancelled = true }
  }, [token, refresh])
  async function save(documentId: string) {
    const version = revision.current
    setBusy(documentId); setNotice('Preparing device cache…')
    try {
      const record = await keepDocumentOnDevice(documentId)
      if (version !== revision.current) return
      setSaved(old => ({ ...old, [documentId]: record.cache_id })); setNotice('Cached on this device')
      await refresh(record.owner_scope_id)
    } catch (error) { if (version === revision.current) setNotice(error instanceof Error ? error.message : 'Could not save an encrypted device copy.') }
    finally { if (version === revision.current) setBusy(null) }
  }
  async function restore(cacheId: string) {
    const version = revision.current
    if (busy) return
    setBusy(cacheId); setNotice('Restoring prepared document…')
    try {
      const document = await restoreDeviceCopy(cacheId, owner)
      if (version !== revision.current) return
      setSaved(old => ({ ...old, [document.document_id]: cacheId })); setNotice('Active this session. Server copies are removed when you log out.')
      await refresh(owner)
      return document
    } catch (error) { if (version === revision.current) setNotice(error instanceof Error ? error.message : 'This device copy could not be restored.') }
    finally { if (version === revision.current) setBusy(null) }
  }
  async function removeCopy(cacheId: string) {
    const version = revision.current
    try {
      await localDocumentCache.remove(cacheId, owner)
      if (version !== revision.current) return
      setSaved(old => Object.fromEntries(Object.entries(old).filter(([, id]) => id !== cacheId)))
      await refresh(owner)
    } catch (error) { if (version === revision.current) reportError(error) }
  }
  async function clear() {
    if (!window.confirm('Remove all encrypted document copies for your account from this device?')) return
    const version = revision.current
    try {
      await localDocumentCache.clearForOwner(owner)
      if (version !== revision.current) return
      setSaved({}); await refresh(owner)
    } catch (error) { if (version === revision.current) reportError(error) }
  }
  function reportError(error: unknown) {
    setNotice(error instanceof Error ? error.message : 'The document request could not be completed.')
  }
  return { reportError, enabled, owner, copies, notice, busy, saved, save, restore, removeCopy, clear }
}
export type DeviceState = ReturnType<typeof useDeviceDocuments>

