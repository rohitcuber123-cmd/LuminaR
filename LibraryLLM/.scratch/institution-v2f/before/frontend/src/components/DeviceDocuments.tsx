import type { RAGDocument } from '../lib/api'
import { removeServerDocument } from '../lib/documentCacheApi'
import type { DeviceState } from '../hooks/useDeviceDocuments'

export function DeviceDocuments({ documents, selectedId, select, reload, device, keep, setKeep }:
  { documents: RAGDocument[]; selectedId: string | null; select: (id: string | null) => void;
    reload: () => Promise<void>; device: DeviceState; keep: boolean; setKeep: (value: boolean) => void }) {
  return <section className="space-y-3 text-xs" aria-label="Private documents">
    {device.enabled && <label className="flex items-start gap-2 px-2">
      <input type="checkbox" checked={keep} onChange={e => setKeep(e.target.checked)} />
      <span>Keep an encrypted copy on this device for faster reuse
        <span className="mt-1 block text-ink-soft">Server copies are still removed when you log out.</span></span>
    </label>}
    <h2 className="px-2 font-semibold">Active this session</h2>
    <p className="px-2 text-ink-soft">Server copies are removed when you log out.</p>
    {!documents.length && <p className="px-2 text-ink-soft">Add a PDF to get started.</p>}
    {documents.map(doc => <div key={doc.document_id} className="border-b border-line pb-2">
      <button className={`w-full px-2 py-2 text-left ${selectedId === doc.document_id ? 'bg-paper text-brand' : ''}`}
        onClick={() => select(selectedId === doc.document_id ? null : doc.document_id)}>
        <span className="block truncate" title={doc.filename}>{doc.filename}</span><span className="text-ink-soft">{doc.pages} pages · Active</span>
      </button>
      <div className="flex flex-wrap gap-2 px-2 text-brand">
        {device.enabled && (device.saved[doc.document_id]
          ? <button onClick={() => void device.removeCopy(device.saved[doc.document_id])}>Remove device copy</button>
          : <button disabled={!!device.busy} onClick={() => void device.save(doc.document_id)}>{device.busy === doc.document_id ? 'Preparing device cache…' : 'Keep on this device'}</button>)}
        <button onClick={async () => {
          try {
            await removeServerDocument(doc.document_id)
            if (selectedId === doc.document_id) select(null)
            await reload()
          } catch (error) { device.reportError(error) }
        }}>Remove server copy</button>
      </div>
    </div>)}
    {device.notice && <p role="status" className="px-2 text-ink-soft">{device.notice}</p>}
    {device.enabled && <div className="border-t border-line pt-3">
      <h2 className="px-2 font-semibold">Cached on this device</h2>
      <p className="mt-1 px-2 text-ink-soft">Encrypted copies stay here until removed. Restore a copy to ask questions.</p>
      {device.copies.map(copy => <div key={copy.record.cache_id} className="space-y-1 border-b border-line px-2 py-3">
        <p className="truncate" title={copy.descriptor?.filename}>{copy.descriptor?.filename || 'Device copy'}</p>
        <p className="text-ink-soft">{copy.record.blob_size < 1048576 ? `${Math.max(1, Math.round(copy.record.blob_size / 1024))} KB` : `${(copy.record.blob_size / 1048576).toFixed(1)} MB`} · {new Date(copy.record.created_at).toLocaleDateString()}</p>
        {copy.error && <p className="text-brand">{copy.error === 'CACHE_INCOMPATIBLE' ? 'Needs reprocessing. Re-upload the original PDF.' : 'Copy could not be verified. Re-upload the original PDF.'}</p>}
        <div className="flex gap-3 text-brand">
          <button disabled={!!device.busy || !!copy.error} onClick={async () => {
            const doc = await device.restore(copy.record.cache_id)
            if (doc) {
              try { await reload(); select(doc.document_id) }
              catch (error) { device.reportError(error) }
            }
          }}>{device.busy === copy.record.cache_id ? 'Restoring…' : 'Restore'}</button>
          <button onClick={() => void device.removeCopy(copy.record.cache_id)}>Remove device copy</button>
        </div>
      </div>)}
      {!!device.copies.length && <button className="mt-3 px-2 text-brand" onClick={() => void device.clear()}>Clear cached documents on this device</button>}
    </div>}
  </section>
}
