/** Ciphertext repository. Filenames/content never enter Web Storage. */
export interface CacheRecord {
  cache_id: string; owner_scope_id: string; encrypted_descriptor: string
  format_version: number; blob_size: number; created_at: number; last_restored_at: number
  opfs_key?: string; blob?: Blob; keep: boolean
}
const DIRECTORY = 'luminar-know-more-cache'
const MAX_DOCS = Number(import.meta.env?.VITE_KNOW_MORE_LOCAL_CACHE_MAX_DOCS || 10)
const MAX_BYTES = Number(import.meta.env?.VITE_KNOW_MORE_LOCAL_CACHE_MAX_BYTES || 134217728)
export class CacheStorageError extends Error {}

export class LocalDocumentCacheRepository {
  private database?: Promise<IDBDatabase>
  private queue: Promise<unknown> = Promise.resolve()
  private idb: IDBFactory | undefined
  private storage: StorageManager | undefined
  constructor(idb: IDBFactory | undefined = globalThis.indexedDB, storage: StorageManager | undefined = globalThis.navigator?.storage) { this.idb = idb; this.storage = storage }
  isSupported() { return !!this.idb }
  async backend(): Promise<'opfs' | 'indexeddb'> {
    if (this.storage?.getDirectory) {
      try { await this.storage.getDirectory(); return 'opfs' } catch { /* Restricted profile: try IndexedDB. */ }
    }
    return 'indexeddb'
  }
  private db() {
    if (!this.idb) throw new CacheStorageError('Device storage is unavailable in this browser.')
    return this.database ??= new Promise<IDBDatabase>((resolve, reject) => {
      const request = this.idb!.open('luminar-private-document-cache', 1)
      request.onupgradeneeded = () => {
        const store = request.result.createObjectStore('copies', { keyPath: 'cache_id' })
        store.createIndex('owner_scope_id', 'owner_scope_id'); store.createIndex('last_restored_at', 'last_restored_at')
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(new CacheStorageError('Device storage could not be opened.'))
    })
  }
  private async records(): Promise<CacheRecord[]> {
    const db = await this.db()
    return new Promise((resolve, reject) => {
      const request = db.transaction('copies').objectStore('copies').getAll()
      request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error)
    })
  }
  private async write(record: CacheRecord | string) {
    const db = await this.db()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('copies', 'readwrite')
      if (typeof record === 'string') tx.objectStore('copies').delete(record)
      else tx.objectStore('copies').put(record)
      tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error)
    })
  }
  private async directory() { return (await this.storage!.getDirectory()).getDirectoryHandle(DIRECTORY, { create: true }) }
  private async deleteFile(key?: string) {
    if (!key) return
    try { await (await this.directory()).removeEntry(key) } catch { /* Missing/evicted files are already removed. */ }
  }
  private serial<T>(operation: () => Promise<T>): Promise<T> {
    const run = async () => globalThis.navigator?.locks
      ? navigator.locks.request('luminar-device-cache', operation) : operation()
    const result = this.queue.then(run, run)
    this.queue = result.catch(() => undefined)
    return result
  }
  async estimateUsage(): Promise<StorageEstimate> { return this.storage?.estimate ? this.storage.estimate() : {} }
  async listForOwner(owner: string) { return (await this.records()).filter(r => r.owner_scope_id === owner).map(({ blob: _blob, ...metadata }) => metadata) }
  async get(cacheId: string, owner: string) {
    const record = (await this.records()).find(r => r.cache_id === cacheId && r.owner_scope_id === owner)
    if (!record) throw new CacheStorageError('This device copy is unavailable.')
    if (record.opfs_key) {
      try { return { record, blob: await (await (await this.directory()).getFileHandle(record.opfs_key)).getFile() } }
      catch { throw new CacheStorageError('This device copy is missing. Re-upload the original PDF or remove the copy.') }
    }
    if (!record.blob) throw new CacheStorageError('This device copy is missing.')
    return { record, blob: record.blob }
  }
  async store(metadata: Omit<CacheRecord, 'created_at' | 'last_restored_at' | 'keep'>, blob: Blob) {
    return this.serial(async () => {
      if (!/^[a-f0-9]{32}$/.test(metadata.cache_id) || !/^[a-f0-9]{64}$/.test(metadata.owner_scope_id)
          || metadata.blob_size !== blob.size || blob.size > MAX_BYTES) throw new CacheStorageError('Invalid device cache metadata.')
      const records = await this.records(), old = records.find(r => r.cache_id === metadata.cache_id)
      if (old && old.owner_scope_id !== metadata.owner_scope_id) throw new CacheStorageError('Invalid device cache scope.')
      const total = records.reduce((sum, r) => sum + r.blob_size, 0) - (old?.blob_size || 0) + blob.size
      const estimate = await this.estimateUsage()
      if ((!old && records.length >= MAX_DOCS) || total > MAX_BYTES
          || (estimate.quota && estimate.usage && estimate.quota - estimate.usage < blob.size * 1.2))
        throw new CacheStorageError('Device cache is full. Remove an unused copy and try again.')
      const record: CacheRecord = { cache_id: metadata.cache_id, owner_scope_id: metadata.owner_scope_id,
        encrypted_descriptor: metadata.encrypted_descriptor, format_version: metadata.format_version,
        blob_size: blob.size, created_at: Date.now(), last_restored_at: 0, keep: true }
      try {
        if (await this.backend() === 'opfs') {
          record.opfs_key = `${metadata.cache_id}-${crypto.randomUUID()}.bin`
          const file = await (await this.directory()).getFileHandle(record.opfs_key, { create: true })
          const writer = await file.createWritable()
          try { await writer.write(blob); await writer.close() } catch (error) { await writer.abort().catch(() => {}); throw error }
        } else record.blob = blob
        await this.write(record)
        await this.deleteFile(old?.opfs_key)
        return record
      } catch {
        await this.deleteFile(record.opfs_key)
        throw new CacheStorageError('Could not save an encrypted device copy. Check available storage.')
      }
    })
  }
  async remove(cacheId: string, owner: string) {
    return this.serial(async () => {
      const record = (await this.records()).find(r => r.cache_id === cacheId && r.owner_scope_id === owner)
      if (!record) return
      await this.write(cacheId); await this.deleteFile(record.opfs_key)
    })
  }
  async clearForOwner(owner: string) { for (const r of await this.listForOwner(owner)) await this.remove(r.cache_id, owner) }
  async markRestored(cacheId: string, owner: string) {
    return this.serial(async () => {
      const record = (await this.records()).find(r => r.cache_id === cacheId && r.owner_scope_id === owner)
      if (record) await this.write({ ...record, last_restored_at: Date.now() })
    })
  }
  async logout(owner: string) {
    await this.queue
    for (const r of await this.listForOwner(owner)) if (!r.keep) await this.remove(r.cache_id, owner)
  }
  async prune() {
    // No silent LRU eviction: quota rejection preserves selected/recent documents.
    if (await this.backend() !== 'opfs') return
    return this.serial(async () => {
      const referenced = new Set((await this.records()).map(r => r.opfs_key))
      const directory = await this.directory()
      for await (const [name] of directory.entries()) if (/^[a-f0-9]{32}-.*\.bin$/.test(name) && !referenced.has(name)) await directory.removeEntry(name)
    })
  }
}
export const localDocumentCache = new LocalDocumentCacheRepository()
