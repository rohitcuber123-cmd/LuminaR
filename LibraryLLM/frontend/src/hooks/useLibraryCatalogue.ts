import { useEffect, useState } from 'react'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { useAuthStore } from '../store/useAuthStore'
import { BORROW_STATE_CHANGED } from '../lib/api'
import { loadCatalogue, type CatalogueOperation } from '../lib/libraryCatalogue'
import { observeCatalogue } from '../lib/catalogueInvalidation'

export function useLibraryCatalogue<T>(operation: CatalogueOperation, filters = '', staff=false) {
  const library = useInstitutionStore(activeLibrary), token = useAuthStore(s => s.token), id = library?.library_id || ''
  const [revision, setRevision] = useState(0)
  const key = `${id}:${token}:${operation}:${filters}:${revision}:${staff}`
  const [result, setResult] = useState<{ key: string; source: string; data?: T; error?: string } | null>(null)
  useEffect(() => {
    if (!id || !token) return
    const controller = new AbortController(); let alive = true
    void loadCatalogue(operation, id, filters, controller.signal,staff).then(data => {
      if (alive && data.source.library_id === id) setResult({ key, source: data.source.catalogue_source, data: data as T })
    }).catch(error => { if (alive) setResult({ key, source: '', error: error instanceof Error ? error.message : 'Unable to load this library catalogue.' }) })
    return () => { alive = false; controller.abort() }
  }, [id, token, operation, filters, key,staff])
  useEffect(() => { const refresh = () => setRevision(r => r + 1); window.addEventListener(BORROW_STATE_CHANGED, refresh); return () => window.removeEventListener(BORROW_STATE_CHANGED, refresh) }, [])
  useEffect(() => observeCatalogue(id, () => setRevision(r => r + 1)), [id])
  return { library, data: result?.key === key ? result.data : undefined, error: result?.key === key ? result.error : undefined,
    loading: result?.key !== key, cacheKey: result?.key === key ? `${key}:${result.source}` : key, retry: () => setRevision(r => r + 1) }
}
