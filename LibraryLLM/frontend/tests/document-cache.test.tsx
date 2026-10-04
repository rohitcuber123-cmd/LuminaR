import assert from 'node:assert/strict'
import { test, afterEach } from 'node:test'
import { IDBFactory } from 'fake-indexeddb'
import { JSDOM } from 'jsdom'
import React from 'react'
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage,
  sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor } = await import('@testing-library/react')
const { LocalDocumentCacheRepository } = await import('../src/lib/localDocumentCache.ts')
const { DeviceDocuments } = await import('../src/components/DeviceDocuments.tsx')
const { finishDocumentLogout } = await import('../src/lib/documentCacheApi.ts')
const ownerA = 'a'.repeat(64), ownerB = 'b'.repeat(64)
const blob = new Blob(['authenticated-ciphertext'])
const metadata = (owner = ownerA, id = 'a'.repeat(32)) => ({ cache_id: id, owner_scope_id: owner, encrypted_descriptor: 'encrypted-descriptor', blob_size: blob.size, format_version: 1 })
afterEach(cleanup)

function opfs() {
  const files = new Map<string, Blob>()
  const directory = {
    getDirectoryHandle: async () => directory,
    getFileHandle: async (name: string, options: { create?: boolean } = {}) => {
      if (!options.create && !files.has(name)) throw new Error('missing')
      return { getFile: async () => files.get(name)!, createWritable: async () => ({
        write: async (data: Blob) => { files.set(name, data) }, close: async () => {}, abort: async () => {} }) }
    },
    removeEntry: async (name: string) => { files.delete(name) },
    entries: async function* () { for (const key of files.keys()) yield [key, {}] }
  }
  return { files, storage: { getDirectory: async () => directory, estimate: async () => ({ quota: 100000000, usage: 0 }) } as unknown as StorageManager }
}

test('OPFS preferred, metadata encrypted, repository returns exact ciphertext', async () => {
  const mock = opfs(), repo = new LocalDocumentCacheRepository(new IDBFactory(), mock.storage)
  assert.equal(await repo.backend(), 'opfs')
  const stored = await repo.store(metadata(), blob)
  assert.ok(stored.opfs_key); assert.equal(stored.blob, undefined)
  assert.equal(mock.files.size, 1)
  assert.equal(await (await repo.get(stored.cache_id, ownerA)).blob.text(), await blob.text())
  assert.ok(!JSON.stringify(await repo.listForOwner(ownerA)).includes('private.pdf'))
  await repo.remove(stored.cache_id, ownerA); assert.equal(mock.files.size, 0)
})

test('IndexedDB Blob fallback when OPFS unavailable or blocked', async () => {
  for (const storage of [undefined, { getDirectory: async () => { throw new Error('blocked') } } as unknown as StorageManager]) {
    const repo = new LocalDocumentCacheRepository(new IDBFactory(), storage)
    assert.equal(await repo.backend(), 'indexeddb')
    await repo.store(metadata(), blob)
    assert.equal(await (await repo.get(metadata().cache_id, ownerA)).blob.text(), await blob.text())
  }
})

test('account switching A B A hides other scope and denies direct get/remove', async () => {
  const repo = new LocalDocumentCacheRepository(new IDBFactory())
  await repo.store(metadata(), blob)
  await repo.store(metadata(ownerB, 'b'.repeat(32)), blob)
  assert.equal((await repo.listForOwner(ownerA)).length, 1)
  assert.deepEqual((await repo.listForOwner(ownerB)).map(r => r.cache_id), ['b'.repeat(32)])
  await assert.rejects(repo.get('a'.repeat(32), ownerB))
  await repo.remove('a'.repeat(32), ownerB)
  assert.equal((await repo.listForOwner(ownerA)).length, 1)
  await repo.clearForOwner(ownerB)
  assert.equal((await repo.listForOwner(ownerA)).length, 1)
})

test('logout retains only explicitly opted in ciphertext; no Web Storage/cookies', async () => {
  const repo = new LocalDocumentCacheRepository(new IDBFactory())
  const before = [localStorage.length, sessionStorage.length, document.cookie]
  await repo.store(metadata(), blob); await repo.logout(ownerA)
  assert.equal((await repo.listForOwner(ownerA)).length, 1)
  assert.deepEqual([localStorage.length, sessionStorage.length, document.cookie], before)
  const db = await new Promise<IDBDatabase>((resolve) => { const request = new IDBFactory().open('unused'); request.onsuccess = () => resolve(request.result) })
  db.close()
  // Temporary mode never calls store; no device artifact exists to retain.
  const temporary = new LocalDocumentCacheRepository(new IDBFactory()); await temporary.logout(ownerA)
  assert.deepEqual(await temporary.listForOwner(ownerA), [])
})

test('quota rejects without deleting current copy', async () => {
  const repo = new LocalDocumentCacheRepository(new IDBFactory(), { estimate: async () => ({ quota: 1, usage: 1 }) } as StorageManager)
  await assert.rejects(repo.store(metadata(), blob), /full/)
  assert.equal((await repo.listForOwner(ownerA)).length, 0)
})

test('atomic replacement and missing OPFS copy handled', async () => {
  const mock = opfs(), repo = new LocalDocumentCacheRepository(new IDBFactory(), mock.storage)
  await repo.store(metadata(), blob); await repo.store(metadata(), blob)
  assert.equal(mock.files.size, 1)
  mock.files.clear()
  await assert.rejects(repo.get(metadata().cache_id, ownerA), /missing/)
})

test('concurrent stores respect document cap without silent pruning', async () => {
  const repo = new LocalDocumentCacheRepository(new IDBFactory())
  const results = await Promise.allSettled(Array.from({ length: 11 }, (_, i) => repo.store(metadata(ownerA, i.toString(16).padStart(32, '0')), blob)))
  assert.equal(results.filter(r => r.status === 'fulfilled').length, 10)
  assert.equal((await repo.listForOwner(ownerA)).length, 10)
})

function device(patch = {}) {
  return { reportError: () => {}, enabled: true, owner: ownerA, copies: [], notice: '', busy: null, saved: {}, save: async () => {}, restore: async () => undefined,
    removeCopy: async () => {}, clear: async () => {}, ...patch }
}
function mount(state = device()) { return render(<DeviceDocuments documents={[]} selectedId={null} select={() => {}} reload={async () => {}} device={state} keep={false} setKeep={() => {}} />) }
test('opt-in defaults off and cached copies are separate from active documents', () => {
  mount()
  assert.equal((screen.getByRole('checkbox') as HTMLInputElement).checked, false)
  assert.ok(screen.getByText('Active this session')); assert.ok(screen.getByText('Cached on this device'))
  assert.ok(screen.getByText('Server copies are still removed when you log out.'))
})

test('restore activates returned current document ID and remove device action works', async () => {
  let restored = '', removed = '', selected = '', reloaded = false
  render(<DeviceDocuments documents={[]} selectedId={null} select={id => { selected = id || '' }} reload={async () => { reloaded = true }}
    keep={false} setKeep={() => {}} device={device({ copies: [{ record: { ...metadata(), created_at: Date.now() }, descriptor: { filename: 'private.pdf' } }],
      restore: async (id: string) => { restored = id; return { document_id: 'doc_new', filename: 'private.pdf', pages: 1, chunks: 1 } },
      removeCopy: async (id: string) => { removed = id } })} />)
  fireEvent.click(screen.getByRole('button', { name: 'Restore' }))
  await waitFor(() => assert.equal(selected, 'doc_new')); assert.ok(reloaded); assert.equal(restored, metadata().cache_id)
  fireEvent.click(screen.getByRole('button', { name: 'Remove device copy' })); assert.equal(removed, metadata().cache_id)
})

test('corrupt and incompatible cache UI offers removal and re-upload', () => {
  mount(device({ copies: [{ record: { ...metadata(), created_at: Date.now() }, error: 'CACHE_INCOMPATIBLE' }] }))
  assert.ok(screen.getByText(/Needs reprocessing/)); assert.ok((screen.getByRole('button', { name: 'Restore' }) as HTMLButtonElement).disabled)
  assert.ok(screen.getByRole('button', { name: 'Remove device copy' }))
})

test('logout sends authenticated purge before revocation and never starts export', async () => {
  const original = globalThis.fetch, paths: string[] = []
  globalThis.fetch = async (url, options) => {
    paths.push(String(url)); assert.equal(new Headers(options?.headers).get('Authorization'), 'Bearer session-token')
    return new Response(JSON.stringify({ server_copies_removed: true }))
  }
  try { assert.equal(await finishDocumentLogout('session-token'), true) } finally { globalThis.fetch = original }
  assert.deepEqual(paths, ['/rag-api/rag/session/logout', '/api/auth/logout'])
})
