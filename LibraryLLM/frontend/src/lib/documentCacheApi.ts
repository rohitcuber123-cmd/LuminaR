import { getToken, type RAGDocument } from './api'
import { localDocumentCache, type CacheRecord } from './localDocumentCache'

export class DocumentCacheError extends Error {
  code: string
  constructor(code: string, message: string) { super(message); this.code = code }
}
let generation = 0
const jobs = new Set<Promise<unknown>>()
let currentScope: string | undefined
async function request(path: string, options: RequestInit = {}) {
  const token = getToken()
  const response = await fetch(`/rag-api/rag/${path}`, { ...options,
    headers: { Authorization: `Bearer ${token}`, ...options.headers } })
  if (token !== getToken()) throw new DocumentCacheError('SESSION_CHANGED', 'The signed-in account changed.')
  if (!response.ok) {
    const body = await response.json().catch(() => ({})), detail = body.detail
    throw new DocumentCacheError(detail?.code || `HTTP_${response.status}`, detail?.message || (typeof detail === 'string' ? detail : 'The document request could not be completed.'))
  }
  return response
}
export interface CacheDescriptor { cache_id: string; filename: string; pages: number; document_sha256: string; pipeline_fingerprint: string; created_at: number }
export interface DeviceCopy { record: Omit<CacheRecord, 'blob'>; descriptor?: CacheDescriptor; error?: string }
export async function documentCacheScope() {
  const scope = await (await request('local-cache/scope')).json()
  currentScope = scope.owner_scope_id
  return scope as { enabled: boolean; owner_scope_id?: string; pipeline_fingerprint?: string }
}
export async function listDeviceCopies(owner: string): Promise<DeviceCopy[]> {
  const records = await localDocumentCache.listForOwner(owner), items: DeviceCopy[] = []
  for (let start = 0; start < records.length; start += 20) {
    const part = records.slice(start, start + 20)
    const response = await (await request('local-cache/inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ descriptors: part.map(r => r.encrypted_descriptor) }) })).json()
    part.forEach((record, i) => items.push({ record, descriptor: response.items[i]?.descriptor, error: response.items[i]?.error?.code }))
  }
  return items
}
export async function keepDocumentOnDevice(documentId: string) {
  const revision = generation
  const job = (async () => {
    const response = await request(`documents/${encodeURIComponent(documentId)}/cache/export`, { method: 'POST' })
    const metadata = JSON.parse(response.headers.get('X-Luminar-Cache') || '{}')
    const blob = await response.blob()
    if (revision !== generation) throw new DocumentCacheError('SESSION_CHANGED', 'Signed out before the device copy was saved.')
    if (navigator.storage?.persist) await navigator.storage.persist().catch(() => false)
    const record = await localDocumentCache.store(metadata, blob)
    // Descriptor inspection is authenticated; content hashes never become plaintext storage.
    const copies = await listDeviceCopies(record.owner_scope_id)
    const fresh = copies.find(c => c.record.cache_id === record.cache_id)?.descriptor
    if (fresh) for (const copy of copies) if (copy.record.cache_id !== record.cache_id && copy.descriptor?.document_sha256 === fresh.document_sha256
        && copy.descriptor.pipeline_fingerprint === fresh.pipeline_fingerprint) await localDocumentCache.remove(copy.record.cache_id, record.owner_scope_id)
    return record
  })()
  jobs.add(job)
  try { return await job } finally { jobs.delete(job) }
}
export async function restoreDeviceCopy(cacheId: string, owner: string) {
  const { blob } = await localDocumentCache.get(cacheId, owner)
  const response = await (await request('local-cache/restore', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: blob })).json()
  await localDocumentCache.markRestored(cacheId, owner)
  return response.document as RAGDocument
}
export async function removeServerDocument(documentId: string) {
  return (await request(`documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })).json()
}
export async function finishDocumentLogout(token: string) {
  generation++
  // Exports start at opt-in, never here. Completed repository writes can settle.
  await Promise.race([Promise.allSettled([...jobs]), new Promise(resolve => setTimeout(resolve, 1500))])
  if (currentScope && localDocumentCache.isSupported()) await localDocumentCache.logout(currentScope).catch(() => {})
  let removed = false
  try {
    const response = await fetch('/rag-api/rag/session/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(5000) })
    if (response.ok) removed = (await response.json()).server_copies_removed === true
  } catch { /* Core revokes even when the RAG worker is offline. */ }
  try { await fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(3000) }) } catch { /* TTL/startup sweeper remains the bounded fallback. */ }
  currentScope = undefined
  return removed
}
