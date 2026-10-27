import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { Modal } from '../components/StaffUI'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole } from '../lib/libraryWorkspace'
import { activeBuild, intelligenceStatus, requestIntelligenceBuild, type IntelligenceStatus, type IntelligenceTarget } from '../lib/libraryIntelligence'
import './LibraryIntelligence.css'

const labels: Record<string,string> = { NOT_BUILT:'Not built', EMPTY:'Not available yet', READY:'Ready', STALE:'Update available', QUEUED:'Queued', BUILDING:'Building', RUNNING:'Building', VALIDATING:'Validating', PUBLISHING:'Publishing', FAILED:'Build failed', RECOVERY_REQUIRED:'Needs recovery', SUCCEEDED:'Succeeded', CANCELLED:'Cancelled' }
const stages: Record<string,string> = { QUEUED:'Waiting for worker', DATASET:'Preparing catalogue snapshot', EMBEDDING:'Embedding books', KG_METADATA:'Building catalogue relationships', VALIDATION:'Validating artifacts', PUBLISH:'Publishing generation', COMPLETE:'Complete', RECOVERED:'Outcome reconciled', FAILED:'Build failed', RECOVERY_REQUIRED:'Needs recovery' }
const date = (value: string | null) => value ? new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value+'Z').toLocaleString(undefined, { dateStyle:'medium', timeStyle:'short' }) : 'Not yet'
const name = (target: IntelligenceTarget) => target.target === 'SEARCH_INDEX' ? 'Search Index' : 'Knowledge Graph'
const actionLabel = (target: IntelligenceTarget) => target.latest_job?.state === 'FAILED' && target.can_retry ? 'Retry Build' : `${target.active_generation_id ? 'Rebuild' : 'Build'} ${name(target)}`

export function LibraryIntelligencePage() {
  const { libraryId = '' } = useParams(), token = useAuthStore(s => s.token)
  return <IntelligenceSession key={`${libraryId}:${token}`} id={libraryId} />
}

function IntelligenceSession({ id }: { id: string }) {
  const library = useInstitutionStore(s => s.libraries.find(l => l.library_id === id))
  const role = libraryRole(library || null)
  const [data,setData] = useState<IntelligenceStatus | null>(null), [error,setError] = useState('')
  const [confirm,setConfirm] = useState<'search' | 'kg' | null>(null), [busy,setBusy] = useState(false)
  const alive = useRef(false), sequence = useRef(0), refresh = useRef<() => void>(() => {})
  const buildController = useRef<AbortController | null>(null)

  useEffect(() => {
    alive.current = true
    const actionController = new AbortController()
    buildController.current = actionController
    let mounted = true
    let timer: ReturnType<typeof setTimeout> | undefined, controller: AbortController | undefined
    async function load() {
      clearTimeout(timer); controller?.abort(); controller = new AbortController()
      const current = ++sequence.current
      try {
        const value = await intelligenceStatus(id,controller.signal)
        if (!mounted || current !== sequence.current) return
        if (value.library_id !== id) throw new Error('Scope mismatch')
        setData(value);setError('')
        if ([value.search,value.kg].some(activeBuild)) timer = setTimeout(() => void load(),3000)
      } catch (reason) {
        if (mounted && current === sequence.current && !(reason instanceof DOMException && reason.name === 'AbortError')) {
          setData(null);setError('Unable to load intelligence status. Refresh to verify current access and build state.')
        }
      }
    }
    refresh.current = () => void load()
    const focus = () => refresh.current()
    if (role === 'ADMIN' || role === 'LIBRARIAN') void load()
    window.addEventListener('focus',focus)
    return () => { mounted=false;alive.current=false;clearTimeout(timer);controller?.abort();actionController.abort();window.removeEventListener('focus',focus) }
  },[id,role])

  async function build() {
    if (!data || !confirm || busy) return
    const target = data[confirm];setBusy(true);setError('')
    try {
      const job = await requestIntelligenceBuild(id,target.target,buildController.current?.signal)
      if (!alive.current) return
      if (job.library_id !== id || job.target !== target.target) throw new Error('Scope mismatch')
      setData(value => value ? {...value,[confirm]:{...target,status:'QUEUED',current_job:job,latest_job:job}} : value)
      setConfirm(null);refresh.current()
    } catch {
      if (alive.current) { setConfirm(null);setData(null);setError('The build request could not be confirmed. Refresh status before trying again.');refresh.current() }
    } finally { if (alive.current) setBusy(false) }
  }

  if (role !== 'ADMIN' && role !== 'LIBRARIAN') return <StatePanel kind="error" title="Staff membership required">Intelligence is available to this library’s Admins and Librarians.</StatePanel>
  return <div className="institutions library-intelligence">
    <PageHeading title="Intelligence" description={`Build and maintain semantic search and knowledge artifacts for ${library?.name || 'this library'}’s catalogue.`} actions={<button className="secondary" disabled={busy} onClick={() => refresh.current()}>Refresh status</button>} />
    <p className="ui-description">Search Index and Knowledge Graph are generated from catalogue metadata. Uploaded PDF, TXT and DOCX contents remain isolated in Digital Assets and document RAG.</p>
    {role === 'LIBRARIAN' && <p className="ui-card">Search and graph builds can be started by Library Admins.</p>}
    {error && <StatePanel kind="error" title="Status unavailable" action={<button onClick={() => refresh.current()}>Retry loading</button>}>{error}</StatePanel>}
    {!data && !error && <StatePanel kind="loading" title="Loading intelligence status…" />}
    {data && <div className="intelligence-grid">{(['search','kg'] as const).map(key => <TargetCard key={key} target={data[key]} data={data} admin={role === 'ADMIN'} busy={busy} onBuild={() => setConfirm(key)} />)}</div>}
    {confirm && data && <Modal title={`${actionLabel(data[confirm])}?`} busy={busy} onClose={() => setConfirm(null)}>
      <p>LuminaR will create a new {confirm === 'search' ? 'semantic-search' : 'knowledge-graph'} generation from the current library catalogue.</p>
      <p>{data[confirm].active_generation_id ? 'The current validated generation will be retained until the new generation passes validation and is published. Catalogue reads continue following the existing safe fallback rules.' : 'The new generation becomes available only after validation and publication. Your library catalogue remains available while it builds.'}</p>
      <div className="ui-actions"><button className="secondary" disabled={busy} onClick={() => setConfirm(null)}>Cancel</button><button disabled={busy} onClick={() => void build()}>{busy ? 'Requesting build…' : actionLabel(data[confirm])}</button></div>
    </Modal>}
  </div>
}

function TargetCard({ target, data, admin, busy, onBuild }: { target: IntelligenceTarget; data: IntelligenceStatus; admin: boolean; busy: boolean; onBuild: () => void }) {
  const running = activeBuild(target), recovery = target.status === 'RECOVERY_REQUIRED'
  const failed = target.latest_job?.state === 'FAILED', empty = data.eligible_book_count === 0
  const state = recovery ? 'RECOVERY_REQUIRED' : running ? target.current_job!.state : failed && target.active_status === 'READY' ? 'READY' : target.status
  const job = target.current_job
  const current = Math.max(0,Math.min(job?.progress_current || 0,job?.progress_total || 0)), total = Math.max(0,job?.progress_total || 0)
  return <section className="ui-card intelligence-card" aria-labelledby={`intelligence-${target.target}`}>
    <h2 id={`intelligence-${target.target}`}>{target.target === 'SEARCH_INDEX' ? 'Semantic Search Index' : 'Knowledge Graph'}</h2>
    <p role="status" aria-live="polite" aria-atomic="true"><span className="ui-badge">{empty && !running && !target.active_generation_id ? 'Not available yet' : labels[state] || 'Status unavailable'}</span></p>
    {empty && <p>Add books to the library before building {target.target === 'SEARCH_INDEX' ? 'semantic search' : 'the graph'}.</p>}
    {target.status === 'NOT_BUILT' && !empty && <p>Your library currently uses standard local catalogue search. No build starts automatically when books are added.</p>}
    {(target.status === 'STALE' || target.active_status === 'STALE') && <p>The catalogue has changed since this generation was built. Rebuild to include the latest metadata; local fallback remains available.</p>}
    {failed && !recovery && <p>Latest build attempt: Build failed. {target.active_generation_id ? 'The previous validated generation is retained.' : 'Standard local catalogue search remains available.'} You can retry this known outcome.</p>}
    {recovery && <p>The previous build outcome needs operator reconciliation. Build and Retry are unavailable until the outcome is safely resolved.</p>}
    <dl><dt>Eligible books</dt><dd>{data.eligible_book_count.toLocaleString()}</dd><dt>{target.target === 'SEARCH_INDEX' ? 'Books indexed' : 'Books represented'}</dt><dd>{target.record_count.toLocaleString()}</dd>
      {target.target === 'KNOWLEDGE_GRAPH' && <><dt>Nodes</dt><dd>{target.node_count?.toLocaleString() ?? 'Not yet'}</dd><dt>Relationships</dt><dd>{target.edge_count?.toLocaleString() ?? 'Not yet'}</dd></>}
      <dt>Active generation</dt><dd>{target.active_generation_id ? `Generation ${target.generation_sequence ?? '—'}` : 'Not yet'}</dd><dt>Last successful build</dt><dd>{date(target.built_at)}</dd>
      <dt>Last build duration</dt><dd>{target.last_build_duration_seconds == null ? 'Not yet' : `${target.last_build_duration_seconds.toFixed(1)} seconds`}</dd>
    </dl>
    {running && job && <div className="intelligence-progress"><p role="status">Stage: {stages[job.stage] || 'Building catalogue artifacts'}</p><label htmlFor={`progress-${target.target}`}>{current} / {total || 'Preparing'} books</label><progress id={`progress-${target.target}`} aria-label={`${name(target)} build progress`} max={total || 1} {...(total ? {value:current} : {})} /></div>}
    <details><summary>Technical details</summary><dl><dt>Current dataset generation</dt><dd>{data.dataset.generation_id || 'Not yet'}</dd><dt>Active source dataset</dt><dd>{target.source_generation_id || 'Not yet'}</dd><dt>Active generation UUID</dt><dd>{target.active_generation_id || 'Not yet'}</dd><dt>Artifact verification</dt><dd>{target.artifact_verified ? 'Verified' : 'No validated generation'}</dd>
      {target.target === 'SEARCH_INDEX' && <><dt>Model</dt><dd>{target.model}</dd><dt>Embedding dimension</dt><dd>{target.dimension}</dd><dt>HNSW M</dt><dd>{target.parameters.M}</dd><dt>efConstruction</dt><dd>{target.parameters.efConstruction}</dd><dt>efSearch</dt><dd>{target.parameters.efSearch}</dd></>}
    </dl></details>
    {admin && data.can_build && !running && !recovery && <button disabled={busy || empty} onClick={onBuild}>{actionLabel(target)}</button>}
  </section>
}
