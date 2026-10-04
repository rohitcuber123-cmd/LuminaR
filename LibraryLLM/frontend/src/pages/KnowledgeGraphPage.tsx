import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Network, Search, ZoomIn, ZoomOut } from 'lucide-react'
import { graphBooks, graphMeta, graphRecommend } from '@/lib/knowledgeGraph'
import type { KGBook, KGNode, KGResponse, GraphMeta } from '@/lib/knowledgeGraph'

const shorten = (text: string, count = 24) => text.length > count ? `${text.slice(0, count - 1)}…` : text
const colour: Record<string, string> = { book: '#235344', author: '#ad663b', subject: '#67628c', topic: '#59789b' }
const nodeColour = (kind: string) => colour[kind] ?? '#777068'

export function KnowledgeGraphPage() {
  const [params] = useSearchParams()
  const initialSeed = params.get('seed') ?? ''
  const [meta, setMeta] = useState<GraphMeta | null>(null)
  const [books, setBooks] = useState<KGBook[]>([])
  const [query, setQuery] = useState('')
  const [seed, setSeed] = useState('')
  const [result, setResult] = useState<KGResponse | null>(null)
  const [selected, setSelected] = useState<KGNode | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [searching, setSearching] = useState(true)
  const [zoom, setZoom] = useState(1)
  const [authors, setAuthors] = useState(true)
  const [subjects, setSubjects] = useState(true)
  const [other, setOther] = useState(true)
  const requestRef = useRef<AbortController | null>(null)
  const lookupRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    lookupRef.current = controller
    Promise.all([graphMeta(controller.signal), graphBooks(initialSeed, controller.signal)]).then(([info, choices]) => {
      if (controller.signal.aborted) return
      requestRef.current?.abort(); setBusy(false); setResult(null); setSelected(null); setError(''); setZoom(1)
      setMeta(info); setBooks(choices.books); setSeed(choices.books[0]?.work_id ?? '')
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Unable to load the graph.') })
      .finally(() => { if (!controller.signal.aborted) setSearching(false) })
    return () => { lookupRef.current?.abort(); requestRef.current?.abort() }
  }, [initialSeed])

  async function search(event: React.FormEvent) {
    event.preventDefault(); lookupRef.current?.abort()
    const controller = new AbortController(); lookupRef.current = controller
    setSearching(true); setError('')
    try {
      const found = await graphBooks(query.trim(), controller.signal)
      if (!controller.signal.aborted) { setBooks(found.books); if (!found.books.some(book => book.work_id === seed)) choose(found.books[0]?.work_id ?? '') }
    } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Search failed.') }
    finally { if (!controller.signal.aborted) setSearching(false) }
  }
  function choose(id: string) {
    requestRef.current?.abort(); setBusy(false); setSeed(id); setResult(null); setSelected(null); setError(''); setZoom(1)
  }
  async function explore(compare = false) {
    if (!seed) return
    requestRef.current?.abort(); const controller = new AbortController(); requestRef.current = controller
    setBusy(true); setError('')
    try {
      const data = await graphRecommend(seed, compare, controller.signal)
      if (!controller.signal.aborted) { setResult(data); setSelected(null); setMeta(data.snapshot) }
    } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Unable to explore this book.') }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  const visible = result?.exploration.nodes.filter(node => node.kind === 'book' || (node.kind === 'author' ? authors : node.kind === 'subject' ? subjects : other)) ?? []
  const features = visible.filter(node => node.kind !== 'book')
  const candidates = visible.filter(node => node.kind === 'book' && !node.seed)
  const height = Math.max(460, features.length * 45 + 70, candidates.length * 55 + 70)
  const position = (node: KGNode) => node.seed ? { x: 135, y: height / 2 } : node.kind === 'book'
    ? { x: 765, y: 45 + candidates.indexOf(node) * (height - 90) / Math.max(1, candidates.length - 1) }
    : { x: 450, y: 45 + features.indexOf(node) * (height - 90) / Math.max(1, features.length - 1) }
  const nodeMap = new Map(visible.map(node => [node.id, node]))
  const related = selected && result ? result.exploration.edges.filter(edge => edge.source === selected.id || edge.target === selected.id).map(edge => nodeMap.get(edge.source === selected.id ? edge.target : edge.source)).filter((node): node is KGNode => Boolean(node)) : []
  const selectedBook = selected?.kind === 'book' && result ? [result.seed, ...result.recommendations].find(book => book.work_id === selected.id) : null

  return <div className="mx-auto max-w-[90rem] px-5 py-10 md:px-10">
    <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
      <div><p className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-[.18em] text-moss"><Network size={15} /> LuminaR Graph Lab <span className="rounded-full border border-moss/25 px-2 py-1 text-[10px] tracking-normal">Experimental</span></p>
        <h1 className="font-serif text-4xl text-moss md:text-5xl">Follow a book’s connections.</h1><p className="mt-3 max-w-2xl text-sm text-ink-soft">Find similar books through shared authors and subjects. Select a node to follow the reason behind a recommendation.</p></div>
      {meta && <div className="text-right text-xs text-ink-soft"><p className="font-semibold text-moss">{meta.books.toLocaleString()} books · {meta.edges.toLocaleString()} links</p><p className="mt-1">Snapshot {new Date(meta.created_at).toLocaleDateString()}</p></div>}
    </div>

    <div className="mb-6 grid items-end gap-4 rounded-2xl border border-line bg-white/60 p-5 lg:grid-cols-[1fr_1.4fr_auto]">
      <form onSubmit={search}><label htmlFor="kg-search" className="mb-2 block text-xs font-bold text-moss">Find a starting book</label><div className="flex gap-2"><input id="kg-search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Title begins with… or work ID" className="min-w-0 flex-1 rounded-lg border border-line bg-paper px-3 py-2 text-sm" /><button disabled={searching} type="submit" aria-label="Search graph books" className="rounded-lg border border-line p-2 disabled:opacity-50"><Search size={18} /></button></div></form>
      <div><label htmlFor="kg-seed" className="mb-2 block text-xs font-bold text-moss">Starting book</label><select id="kg-seed" value={seed} onChange={event => choose(event.target.value)} disabled={searching || !books.length} className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm">{books.map(book => <option key={book.work_id} value={book.work_id}>{book.title}</option>)}{seed && !books.some(book => book.work_id === seed) && <option value={seed}>{result?.seed.title ?? seed}</option>}</select>{!searching && !books.length && <p className="mt-2 text-xs">No matching titles. Try a shorter title prefix or a work ID.</p>}</div>
      <button disabled={!seed || busy || searching} onClick={() => void explore()} className="flex items-center justify-center gap-2 rounded-lg bg-moss px-5 py-2.5 text-sm font-semibold text-paper disabled:opacity-50">{busy ? 'Finding connections…' : 'Explore connections'}<ArrowRight size={16} /></button>
    </div>
    {error && <p role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</p>}
    <div aria-live="polite" className="sr-only">{busy ? 'Loading graph connections' : result ? `${result.recommendations.length} graph recommendations loaded` : searching ? 'Loading catalogue graph' : ''}</div>
    {!result && !error && <div className="rounded-2xl border border-dashed border-line px-6 py-20 text-center"><Network className="mx-auto mb-4 text-moss/50" size={38} /><h2 className="font-serif text-2xl text-moss">Start with a book you know.</h2><p className="mt-2 text-sm text-ink-soft">Explore its connections, then compare the two recommendation lists.</p></div>}
    {result && <>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0 rounded-2xl border border-line bg-white/60" aria-label="Interactive catalogue graph">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4"><div><h2 className="font-serif text-xl text-moss">The connection map</h2><p className="text-xs text-ink-soft">Starting book → shared metadata → similar books</p></div><div className="flex items-center gap-3 text-xs"><label className="flex gap-1.5"><input type="checkbox" checked={authors} onChange={event => setAuthors(event.target.checked)} />Authors</label><label className="flex gap-1.5"><input type="checkbox" checked={subjects} onChange={event => setSubjects(event.target.checked)} />Subjects</label>{result.exploration.nodes.some(node => !['book', 'author', 'subject'].includes(node.kind)) && <label className="flex gap-1.5"><input type="checkbox" checked={other} onChange={event => setOther(event.target.checked)} />Other relationships</label>}<button aria-label="Zoom out" onClick={() => setZoom(value => Math.max(.7, value - .15))}><ZoomOut size={18} /></button><button aria-label="Zoom in" onClick={() => setZoom(value => Math.min(1.8, value + .15))}><ZoomIn size={18} /></button></div></div>
          <div className="overflow-auto p-3"><svg viewBox={`0 0 900 ${height}`} width={900 * zoom} height={height * zoom} className="max-w-none" aria-label="Select a book, author or subject to inspect its links">
            {result.exploration.edges.map(edge => { const source = nodeMap.get(edge.source), target = nodeMap.get(edge.target); if (!source || !target) return null; const a = position(source), b = position(target); const focus = selected && (edge.source === selected.id || edge.target === selected.id); return <path key={`${edge.source}:${edge.target}`} d={`M ${a.x} ${a.y} C ${(a.x + b.x) / 2} ${a.y}, ${(a.x + b.x) / 2} ${b.y}, ${b.x} ${b.y}`} fill="none" stroke={focus ? nodeColour(target.kind) : '#d5ddd5'} strokeWidth={focus ? 3 : 1.3} opacity={selected && !focus ? .25 : 1} /> })}
            {visible.map(node => { const p = position(node); return <g key={node.id} role="button" tabIndex={0} aria-label={`Inspect ${node.kind}: ${node.label}`} onClick={() => setSelected(node)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelected(node) } }} style={{ cursor: 'pointer' }}><title>{node.label}</title><rect x={p.x - 115} y={p.y - 17} width={230} height={34} rx={node.kind === 'book' ? 8 : 17} fill={selected?.id === node.id || node.seed ? nodeColour(node.kind) : '#f8f7f0'} stroke={nodeColour(node.kind)} strokeWidth={selected?.id === node.id ? 2.5 : 1} /><text x={p.x} y={p.y + 4} textAnchor="middle" fontSize={12} fill={selected?.id === node.id || node.seed ? '#fff' : nodeColour(node.kind)}>{shorten(node.label, 32)}</text></g> })}
          </svg></div><p className="border-t border-line p-4 text-xs text-ink-soft">Showing the strongest three reason paths per book. All shared paths contribute to the similarity score. Scroll the map horizontally on smaller screens.</p>
        </section>
        <aside className="rounded-2xl border border-line bg-white/60 p-5" aria-label="Graph node details"><p className="mb-3 text-xs font-bold uppercase tracking-widest text-ink-soft">Inspect a connection</p>{selected ? <><span className="text-xs capitalize" style={{ color: nodeColour(selected.kind) }}>{selected.seed ? 'Starting book' : selected.kind}</span><h3 className="my-2 font-serif text-2xl text-moss">{selected.label}</h3>{selectedBook && <><p className="mb-4 text-sm text-ink-soft">{selectedBook.authors.join(' · ') || 'Author metadata unavailable'}</p><Link className="text-sm font-semibold text-moss underline" to={`/book/${encodeURIComponent(selectedBook.work_id)}`}>Open book details</Link>{!selected.seed && <button onClick={() => choose(selected.id)} className="mt-4 w-full rounded-lg border border-moss px-3 py-2 text-sm text-moss">Use as starting book</button>}</>}<p className="mb-2 mt-6 text-xs font-semibold text-moss">Visible links</p><ul className="space-y-2">{related.map(node => <li key={node.id}><button className="text-left text-sm text-ink-soft hover:text-moss" onClick={() => setSelected(node)}>{node.label}</button></li>)}</ul></> : <p className="text-sm leading-relaxed text-ink-soft">Select a node to highlight its paths and inspect the metadata that connects these books.</p>}<div className="mt-6 border-t border-line pt-4 text-xs leading-relaxed text-ink-soft">Connections come from catalogue author names and subject labels. Shared names have not been resolved into verified author identities.</div></aside>
      </div>
      <div className="my-7 flex flex-wrap items-center justify-between gap-4"><div><h2 className="font-serif text-2xl text-moss">More like “{result.seed.title}”</h2><p className="mt-1 text-xs text-ink-soft">{result.candidate_count.toLocaleString()} connected candidates · top {result.recommendations.length} shown</p></div><button disabled={busy} onClick={() => void explore(true)} className="rounded-lg border border-moss px-5 py-2.5 text-sm font-semibold text-moss disabled:opacity-50">Compare with existing recommender</button></div>
      {result.metrics && <div className="mb-5 grid gap-3 rounded-xl border border-line bg-white/60 p-5 sm:grid-cols-3" role="region" aria-label="Recommendation comparison metrics"><div><p className="text-xs text-ink-soft">List overlap</p><p className="mt-1 font-serif text-2xl text-moss">{Math.round(result.metrics.overlap_at_k * 100)}%</p><p className="text-xs text-ink-soft">{result.metrics.intersection_count} shared books</p></div><div><p className="text-xs text-ink-soft">New graph candidates</p><p className="mt-1 font-serif text-2xl text-moss">{result.metrics.kg_only_ids.length}</p><p className="text-xs text-ink-soft">Absent from the existing top ten</p></div><div><p className="text-xs text-ink-soft">Subject diversity · existing / graph</p><p className="mt-1 font-serif text-2xl text-moss">{result.metrics.existing_diversity.subject_pairwise_distance?.toFixed(2) ?? '—'} / {result.metrics.kg_diversity.subject_pairwise_distance?.toFixed(2) ?? '—'}</p><p className="text-xs text-ink-soft">Higher means less subject overlap</p></div><p className="text-xs text-ink-soft sm:col-span-3">List overlap and metadata diversity measure different recommendations; they do not establish which list is more relevant. Catalogue coverage across seeds is measured in the KG3 report.</p></div>}
      <div className={`grid gap-6 ${result.existing ? 'lg:grid-cols-2' : ''}`}><section><h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-moss">Graph recommender</h3>{!result.recommendations.length && <p className="rounded-xl border border-line p-5 text-sm">No connected recommendations were found for this book.</p>}<ol className="space-y-3">{result.recommendations.map((book, index) => <li key={book.work_id} className="rounded-xl border border-line bg-white/60 p-4"><div className="flex gap-3"><span className="text-sm text-ink-soft">{String(index + 1).padStart(2, '0')}</span><div className="min-w-0 flex-1"><Link to={`/book/${encodeURIComponent(book.work_id)}`} className="font-serif text-lg text-moss hover:underline">{book.title}</Link><p className="mt-1 text-xs text-ink-soft">{book.authors.join(' · ')}</p><p className="mt-2 text-xs text-ink-soft">Similarity {book.score.toFixed(3)}</p><ul className="mt-2 space-y-1">{book.reason_paths.slice(0, 3).map(path => <li key={path.nodes[1]} className="text-xs"><button onClick={() => setSelected(result.exploration.nodes.find(node => node.id === path.nodes[1]) ?? null)} className="text-left text-moss underline">Shared {path.kind}: {path.label}</button></li>)}</ul><details className="mt-3 text-xs text-ink-soft"><summary className="cursor-pointer">All reason paths and catalogue evidence</summary><ul className="mt-2 space-y-2">{book.reason_paths.map(path => <li key={path.nodes[1]}>{result.seed.title} → {path.label} → {book.title}<br />Score contribution {path.contribution.toFixed(4)} · {path.catalogue_degree.toLocaleString()} linked books<ul className="mt-1 space-y-1">{path.provenance.map(evidence => <li key={evidence.work_id}>{evidence.work_id} · {evidence.field}: {evidence.value}</li>)}</ul></li>)}</ul></details></div></div></li>)}</ol></section>{result.existing && <section><h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-moss">Existing recommender</h3><ol className="space-y-3">{result.existing.map((book, index) => <li key={book.work_id} className="rounded-xl border border-line bg-white/60 p-4"><div className="flex gap-3"><span className="text-sm text-ink-soft">{String(index + 1).padStart(2, '0')}</span><div><Link to={`/book/${encodeURIComponent(book.work_id)}`} className="font-serif text-lg text-moss hover:underline">{book.title}</Link><p className="mt-1 text-xs text-ink-soft">{book.authors.join(' · ')}</p><p className="mt-2 text-xs text-ink-soft">{book.subjects.slice(0, 4).join(' · ')}</p></div></div></li>)}</ol></section>}</div>
    </>}
  </div>
}
