import { LuminarSelect } from '../LuminarSelect'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../../store/useAuthStore'
import { generateArtifact, getSource, gradeCloze, listArtifacts, type Artifact, type ArtifactKind, type Card, type QuizQuestionType, type Source } from '../../lib/knowledgeArtifacts'
import { Quiz } from './Quiz'
import { KnowledgeMap } from './KnowledgeMap'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'
import type { LibraryAssetTarget } from '../../lib/libraryAssets'
import { ApiError } from '../../lib/api'

const tabs: [ArtifactKind, string, string][] = [
  ['key-concepts', 'Key Concepts', 'KEY_CONCEPTS'], ['summary', 'Summary', 'EXTRACTIVE_SUMMARY'],
  ['flashcards', 'Flashcards', 'FLASHCARDS'], ['mindmap', 'Mind Map', 'MIND_MAP'], ['quiz', 'Quiz', 'QUIZ'],
]
const quizTypes: [QuizQuestionType, string][] = [['mcq', 'Multiple Choice'], ['fill_blank', 'Fill in the Blanks'], ['matching', 'Match the Following']]
const cardNames: Record<Card['type'], string> = { definition: 'Definition', cloze: 'Cloze', concept: 'Concept', relationship: 'Relationship', process: 'Process step', application: 'Example / application', comparison: 'Comparison' }
const sameQuiz = (a: Artifact, types: QuizQuestionType[]) => a.type === 'QUIZ' && a.options.questionCount === 12
  && a.options.questionTypes?.slice().sort().join(',') === types.slice().sort().join(',')

function Flashcards({ cards, onSource }: { cards: Card[]; onSource: (id: string) => void }) {
  const [filter, setFilter] = useState('all'), [index, setIndex] = useState(0), [flipped, setFlipped] = useState(false)
  const filtered = cards.filter(card => filter === 'all' || card.type === filter)
  const safeIndex = Math.min(index, Math.max(0, filtered.length - 1)), card = filtered[safeIndex]
  const move = useCallback((next: number) => { setIndex(Math.max(0, Math.min(next, filtered.length - 1))); setFlipped(false) }, [filtered.length])
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (!card || event.altKey || event.ctrlKey || event.metaKey || target?.closest('input,textarea,select,button,a,[contenteditable="true"],[role="dialog"]')) return
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); move(safeIndex + (event.key === 'ArrowRight' ? 1 : -1)) }
      else if (event.key === ' ' || event.key === 'Enter') { event.preventDefault(); setFlipped(value => !value) }
    }
    window.addEventListener('keydown', keyboard)
    return () => window.removeEventListener('keydown', keyboard)
  }, [card, safeIndex, move])
  return <div>
    <label className="text-sm">Card type <LuminarSelect className="knowledge-tool-select" value={filter} onChange={e => { setFilter(e.target.value); move(0) }}>
      <option value="all">All</option>{[...new Set(cards.map(c => c.type))].map(type => <option key={type} value={type}>{cardNames[type]}</option>)}
    </LuminarSelect></label>
    {!card ? <p role="status" className="mt-5">Not enough reliable content was found for this card type. Try another filter.</p> : <>
      <p className="my-4 text-sm text-ink-soft">{cardNames[card.type]}</p>
      <div tabIndex={0} aria-label="Flashcard" className="border border-line bg-panel p-5 focus-visible:outline-2 focus-visible:outline-brand sm:p-8">
        <p className="mb-2 text-xs uppercase text-ink-soft">{flipped ? 'Answer' : 'Front'}</p>
        <p className="whitespace-pre-line text-lg leading-relaxed" aria-live="polite">{flipped ? card.back : card.front}</p>
        <button className={toolButton + ' mt-4'} onClick={() => setFlipped(v => !v)}>{flipped ? 'Show front' : 'Reveal answer'}</button>
        <SourceLink source={card} onSource={onSource} />
      </div>
      <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-2"><button className={toolButton + ' justify-self-start'} disabled={safeIndex === 0} onClick={() => move(safeIndex - 1)}>← Previous</button><p className="text-center text-xs text-ink-soft" aria-live="polite">Card {safeIndex + 1} of {filtered.length}</p><button className={toolButton + ' justify-self-end'} disabled={safeIndex === filtered.length - 1} onClick={() => move(safeIndex + 1)}>Next →</button></div>
    </>}
  </div>
}

// A session/document key in the parent discards every piece of private display state on a switch.
export function KnowledgeTools({ documentId, title, libraryAsset }: { documentId: string; title: string; libraryAsset?: LibraryAssetTarget }) {
  const token = useAuthStore(state => state.token)
  return <KnowledgeToolsSession key={`${token}:${libraryAsset?.libraryId || 'personal'}:${documentId}`} documentId={documentId} title={title} libraryAsset={libraryAsset} />
}

function KnowledgeToolsSession({ documentId, title, libraryAsset }: { documentId: string; title: string; libraryAsset?: LibraryAssetTarget }) {
  const [tab, setTab] = useState<ArtifactKind>('flashcards'), [mode, setMode] = useState('quick')
  const [questionTypes, setQuestionTypes] = useState<QuizQuestionType[]>(['mcq', 'fill_blank'])
  const [legacyId, setLegacyId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([]), [loading, setLoading] = useState(true), [generating, setGenerating] = useState(false)
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [source, setSource] = useState<Source | null>(null), [sourceLoading, setSourceLoading] = useState(false)
  const controller = useRef<AbortController | null>(null), sourceController = useRef<AbortController | null>(null)
  const generationInFlight = useRef(false)
  const sourcePreview = useRef<HTMLElement | null>(null)
  useEffect(() => { if (source) sourcePreview.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' }) }, [source])
  const rejectTool = useCallback((reason: unknown, fallback: string) => {
    if (libraryAsset && reason instanceof ApiError && [401, 403, 404].includes(reason.status)) {
      setArtifacts([]); setSource(null); setLegacyId(null); setNotice('')
    }
    setError(reason instanceof Error ? reason.message : fallback)
  }, [libraryAsset])
  const load = useCallback(() => {
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    listArtifacts(documentId, abort.signal, libraryAsset).then(result => { if (!abort.signal.aborted) {
      setArtifacts(result.artifacts)
      const saved = result.artifacts.find(a => a.type === 'QUIZ' && a.options.questionCount === 12 && a.options.questionTypes?.length
        && a.options.questionTypes.every(type => quizTypes.some(([value]) => value === type)))
      if (saved?.options.questionTypes) setQuestionTypes(saved.options.questionTypes)
    } })
      .catch(e => { if (!abort.signal.aborted) rejectTool(e, 'Unable to load study artifacts.') }).finally(() => { if (!abort.signal.aborted) setLoading(false) })
  }, [documentId, libraryAsset, rejectTool])
  useEffect(() => { load(); return () => { controller.current?.abort(); sourceController.current?.abort() } }, [load])
  const artifact = tab === 'quiz' ? artifacts.find(a => legacyId ? a.id === legacyId : sameQuiz(a, questionTypes))
    : artifacts.find(a => a.type === tabs.find(t => t[0] === tab)?.[2] && (tab !== 'summary' || a.options.mode === mode))
  const legacy = artifacts.find(a => a.type === 'QUIZ' && !a.options.questionTypes)
  const generate = async () => {
    if (generationInFlight.current || (tab === 'quiz' && !questionTypes.length)) return
    generationInFlight.current = true
    const abort = new AbortController(); controller.current = abort
    setGenerating(true); setError(''); setNotice('')
    try {
      const result = await generateArtifact(documentId, tab, mode, abort.signal, tab === 'quiz' ? { questionTypes, questionCount: 12 } : undefined, libraryAsset)
      if (!abort.signal.aborted) {
        setArtifacts(current => tab === 'quiz' ? [result.artifact, ...current.filter(a => a.id !== result.artifact.id && !sameQuiz(a, questionTypes))]
          : [...current.filter(a => a.id !== result.artifact.id), result.artifact])
        setLegacyId(null); setNotice(result.cached ? 'Loaded saved artifact.' : libraryAsset ? 'Artifact generated and saved for this library document.' : 'Artifact generated and saved for this session.')
      }
    } catch (e) { if (!abort.signal.aborted) rejectTool(e, 'Unable to generate this artifact.') }
    finally { generationInFlight.current = false; if (!abort.signal.aborted) setGenerating(false) }
  }
  const viewSource = async (chunk: string) => {
    sourceController.current?.abort(); const abort = new AbortController(); sourceController.current = abort
    setSource(null); setSourceLoading(true); setError('')
    try { const result = await getSource(documentId, chunk, abort.signal, libraryAsset); if (!abort.signal.aborted) setSource(result) }
    catch (e) { if (!abort.signal.aborted) rejectTool(e, 'Source unavailable.') }
    finally { if (!abort.signal.aborted) setSourceLoading(false) }
  }
  const content = artifact?.content
  const empty = content && (tab === 'quiz' ? !content.questions?.length : !Object.values(content).some(value => Array.isArray(value) && value.length > 0))
  const isMap = tab === 'mindmap'
  const sourceContent = <>
    {sourceLoading && <p role="status">Loading source…</p>}
    {isMap && error && <p role="alert" className="mt-3 text-sm">{error}</p>}
    {source && <aside ref={sourcePreview} aria-label="Source excerpt" className="mt-3 border border-line bg-panel p-4"><div className="flex items-start justify-between gap-3"><h3 className="break-words font-medium">{source.filename} · {source.pageStart ? `Page ${source.pageStart}` : 'Page unknown'}</h3><button className={toolButton} onClick={() => setSource(null)}>Close source</button></div><blockquote className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed">{source.text}</blockquote></aside>}
  </>
  return <section aria-label="Knowledge Tools" className="knowledge-tools-shell flex min-h-0 min-w-0 flex-1 flex-col">
    <div className={isMap ? 'flex min-h-0 flex-1 flex-col overflow-y-auto p-3 sm:p-4' : 'min-h-0 flex-1 overflow-y-auto p-4 sm:p-6'} data-knowledge-scroll>
    <div className={isMap ? 'flex min-h-0 min-w-0 flex-1 flex-col gap-3' : 'mx-auto max-w-4xl space-y-5'}>
      {isMap ? <h2 className="shrink-0 truncate font-display text-base" title={title}>{title} · Mind Map</h2> : <div><h2 className="break-words font-display text-xl">{title}</h2><p className="mt-2 text-sm text-ink-soft">Knowledge Tools · Entire Document</p><p className="mt-1 text-xs text-ink-soft">{libraryAsset ? 'Source-based concepts and practice materials for this library document. Access follows current library permissions.' : 'Source-based concepts and practice materials. Saved until this document’s session ends.'}</p></div>}
      <div role="tablist" aria-label="Artifact types" className="flex flex-wrap gap-2">{tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} aria-controls="knowledge-content" className={tab === id ? toolButton.replace('hover:bg-panel', 'hover:bg-brand') + ' bg-brand text-paper' : toolButton} disabled={generating} onClick={() => { setTab(id); setSource(null); setNotice('') }}>{label}</button>)}</div>
      {tab === 'summary' && <label className="block text-sm">Summary length <LuminarSelect className="knowledge-tool-select" disabled={generating} value={mode} onChange={e => setMode(e.target.value)}><option value="quick">Quick · up to 5 sentences</option><option value="detailed">Detailed · up to 12 sentences</option></LuminarSelect></label>}
      {tab === 'quiz' && <div className="space-y-3">
        <fieldset disabled={loading || generating} className="border border-line bg-panel p-4">
          <legend className="px-1 text-sm font-medium">Question Types</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-3">{quizTypes.map(([type, label]) => <label key={type} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={questionTypes.includes(type)} className="accent-brand focus-visible:outline-2 focus-visible:outline-brand"
              onChange={e => { const selected = e.currentTarget.checked; setQuestionTypes(current => selected ? [...current, type] : current.filter(value => value !== type)); setLegacyId(null); setNotice(''); setSource(null) }} />{label}
          </label>)}</div>
        </fieldset>
        {!questionTypes.length && <p role="alert" className="text-sm text-ink-soft">Select at least one question type.</p>}
        <button className={toolButton} disabled={loading || generating || !questionTypes.length} onClick={generate}>{generating ? 'Generating…' : 'Generate Quiz'}</button>
        {legacy && !legacyId && <button className={toolButton + ' ml-2'} disabled={generating || loading} onClick={() => setLegacyId(legacy.id)}>View previously saved quiz</button>}
        {legacyId && <p role="status" className="text-sm text-ink-soft">This saved quiz uses the earlier format. Generate Quiz to apply your selected question types.</p>}
      </div>}
      {error && (!isMap || !content?.nodes) && <div role="alert" className="border border-line p-3"><p>{error}</p><button className={toolButton + ' mt-2'} disabled={loading || generating} onClick={() => { setLoading(true); setError(''); load() }}>Retry loading</button></div>}
      {generating && <p role="status" aria-live="polite" className="border-l-2 border-brand bg-panel p-4">Analyzing the document and preparing source-backed {tabs.find(t => t[0] === tab)?.[1].toLowerCase()}…</p>}
      {loading ? <p role="status">Loading saved artifacts…</p> : <div role="tabpanel" id="knowledge-content" aria-label={tabs.find(t => t[0] === tab)?.[1]} className={isMap ? 'flex min-h-0 flex-1 flex-col' : undefined}>
        {!artifact && <div className="border border-line bg-panel p-5"><p>{tab === 'quiz' ? 'No saved quiz for these question types yet.' : `No saved ${tabs.find(t => t[0] === tab)?.[1].toLowerCase()} yet.`}</p>{tab !== 'quiz' && <button className={toolButton + ' mt-4'} disabled={generating} onClick={generate}>{generating ? 'Generating…' : 'Generate'}</button>}</div>}
        {notice && <p role="status" className="mb-3 text-sm text-ink-soft">{notice}</p>}
        {artifact?.analysis?.sampled && <p className="mb-3 text-sm text-ink-soft">This large document was sampled across its chunks. Some topics may be absent.</p>}
        {tab === 'quiz' && content?.questions && <p className="mb-3 text-sm text-ink-soft">Generated {content.learningItemCount ?? content.questions.length} of {content.requestedCount ?? artifact?.options.questionCount ?? 12} requested {questionTypes.includes('matching') && content.matchingAllocation ? 'learning items' : 'questions'}. {quizTypes.filter(([type]) => questionTypes.includes(type)).map(([type, label]) => type === 'matching' && content.matchingAllocation ? `${content.matchingAllocation.sets} matching ${content.matchingAllocation.sets === 1 ? 'set' : 'sets'} · ${content.matchingAllocation.pairs} pairs` : `${label}: ${content.generatedCounts?.[type] ?? content.questions?.filter(q => q.type === type).length ?? 0}`).join(' · ')}</p>}
        {tab === 'quiz' && content?.messages?.map(message => <p key={message} role="status" className="mb-3 text-sm text-ink-soft">{message}</p>)}
        {empty && <p role="status" className="border border-line p-5">{tab === 'flashcards' ? 'Not enough definition-style content was found in this document to create reliable flashcards or cloze cards.' : 'Not enough reliable source content was found for this artifact.'}</p>}
        {content?.concepts && !empty && <ul className="grid items-start gap-4 lg:grid-cols-2">{content.concepts.map(c => <li key={c.id} className="border border-line bg-panel p-4 sm:p-5"><h3 className="font-medium">{c.label}</h3>{c.explanation && <p className="mt-2 text-sm leading-relaxed text-ink-soft">{c.explanation}</p>}<SourceLink source={c} onSource={viewSource} /></li>)}</ul>}
        {content?.sections?.length ? <div className="space-y-5">{content.sections.map((section, i) => <section key={i} className="border border-line p-4"><h3 className="mb-2 font-medium">{section.title}</h3>{section.sentences.map((s, j) => <div key={j}><p className="whitespace-pre-line text-sm leading-relaxed">{s.text}</p><SourceLink source={s} onSource={viewSource} /></div>)}</section>)}</div> : content?.sentences && !empty && <ol className="space-y-4">{content.sentences.map((s, i) => <li key={i} className="border border-line p-4"><p className="whitespace-pre-line leading-relaxed">{s.text}</p><SourceLink source={s} onSource={viewSource} /></li>)}</ol>}
        {content?.cards && !empty && <Flashcards key={artifact?.id} cards={content.cards} onSource={viewSource} />}
        {content?.nodes && !empty && <KnowledgeMap nodes={content.nodes} edges={content.edges || []} onSource={viewSource} sourcePanel={source || sourceLoading || error ? sourceContent : null} />}
        {content?.questions && !empty && <Quiz key={artifact?.id} questions={content.questions} onSource={viewSource}
          onGrade={async (itemId, answer, signal) => {
            try { return await gradeCloze(documentId, artifact!.id, itemId, answer, signal, libraryAsset) }
            catch (reason) { if (libraryAsset && !signal?.aborted) rejectTool(reason, 'Unable to check this answer.'); throw reason }
          }} />}
      </div>}
      {!isMap && sourceContent}
    </div>
    </div>
  </section>
}
