import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../../store/useAuthStore'
import { generateArtifact, getSource, listArtifacts, type Artifact, type ArtifactKind, type Card, type QuizQuestionType, type Source } from '../../lib/knowledgeArtifacts'
import { Quiz } from './Quiz'
import { KnowledgeMap } from './KnowledgeMap'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'

const tabs: [ArtifactKind, string, string][] = [
  ['key-concepts', 'Key Concepts', 'KEY_CONCEPTS'], ['summary', 'Summary', 'EXTRACTIVE_SUMMARY'],
  ['flashcards', 'Flashcards', 'FLASHCARDS'], ['mindmap', 'Mind Map', 'MIND_MAP'], ['quiz', 'Quiz', 'QUIZ'],
]
const quizTypes: [QuizQuestionType, string][] = [['mcq', 'Multiple Choice'], ['fill_blank', 'Fill in the Blanks'], ['matching', 'Match the Following']]
const sameQuiz = (a: Artifact, types: QuizQuestionType[]) => a.type === 'QUIZ' && a.options.questionCount === 12
  && a.options.questionTypes?.slice().sort().join(',') === types.slice().sort().join(',')

function Flashcards({ cards, onSource }: { cards: Card[]; onSource: (id: string) => void }) {
  const [filter, setFilter] = useState('all'), [index, setIndex] = useState(0), [flipped, setFlipped] = useState(false)
  const filtered = cards.filter(card => filter === 'all' || card.type === filter), card = filtered[index]
  const move = (next: number) => { setIndex(next); setFlipped(false) }
  return <div>
    <label className="text-sm">Card type <select className="ml-2 border border-line bg-paper p-2" value={filter} onChange={e => { setFilter(e.target.value); move(0) }}>
      <option value="all">All</option><option value="definition">Definition</option><option value="cloze">Cloze</option>
    </select></label>
    {!card ? <p role="status" className="mt-5">Not enough reliable content was found for this card type. Try another filter.</p> : <>
      <p className="my-4 text-sm text-ink-soft">Card {index + 1} of {filtered.length} · {card.type}</p>
      <div className="border border-line bg-panel p-5 sm:p-8">
        <p className="mb-2 text-xs uppercase text-ink-soft">{flipped ? 'Answer' : 'Front'}</p>
        <p className="min-h-24 whitespace-pre-line text-lg leading-relaxed" aria-live="polite">{flipped ? card.back : card.front}</p>
        <button className={toolButton + ' mt-4'} onClick={() => setFlipped(v => !v)}>{flipped ? 'Show front' : 'Reveal answer'}</button>
        <SourceLink source={card} onSource={onSource} />
      </div>
      <div className="mt-4 flex justify-between gap-3"><button className={toolButton} disabled={index === 0} onClick={() => move(index - 1)}>Previous</button><button className={toolButton} disabled={index === filtered.length - 1} onClick={() => move(index + 1)}>Next</button></div>
    </>}
  </div>
}

// A session/document key in the parent discards every piece of private display state on a switch.
export function KnowledgeTools({ documentId, title }: { documentId: string; title: string }) {
  const token = useAuthStore(state => state.token)
  return <KnowledgeToolsSession key={`${token}:${documentId}`} documentId={documentId} title={title} />
}

function KnowledgeToolsSession({ documentId, title }: { documentId: string; title: string }) {
  const [tab, setTab] = useState<ArtifactKind>('flashcards'), [mode, setMode] = useState('quick')
  const [questionTypes, setQuestionTypes] = useState<QuizQuestionType[]>(['mcq', 'fill_blank'])
  const [legacyId, setLegacyId] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([]), [loading, setLoading] = useState(true), [generating, setGenerating] = useState(false)
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [source, setSource] = useState<Source | null>(null), [sourceLoading, setSourceLoading] = useState(false)
  const controller = useRef<AbortController | null>(null), sourceController = useRef<AbortController | null>(null)
  const load = useCallback(() => {
    controller.current?.abort()
    const abort = new AbortController(); controller.current = abort
    listArtifacts(documentId, abort.signal).then(result => { if (!abort.signal.aborted) {
      setArtifacts(result.artifacts)
      const saved = result.artifacts.find(a => a.type === 'QUIZ' && a.options.questionCount === 12 && a.options.questionTypes?.length
        && a.options.questionTypes.every(type => quizTypes.some(([value]) => value === type)))
      if (saved?.options.questionTypes) setQuestionTypes(saved.options.questionTypes)
    } })
      .catch(e => { if (!abort.signal.aborted) setError(e.message) }).finally(() => { if (!abort.signal.aborted) setLoading(false) })
  }, [documentId])
  useEffect(() => { load(); return () => { controller.current?.abort(); sourceController.current?.abort() } }, [load])
  const artifact = tab === 'quiz' ? artifacts.find(a => legacyId ? a.id === legacyId : sameQuiz(a, questionTypes))
    : artifacts.find(a => a.type === tabs.find(t => t[0] === tab)?.[2] && (tab !== 'summary' || a.options.mode === mode))
  const legacy = artifacts.find(a => a.type === 'QUIZ' && !a.options.questionTypes)
  const generate = async () => {
    if (generating || (tab === 'quiz' && !questionTypes.length)) return
    const abort = new AbortController(); controller.current = abort
    setGenerating(true); setError(''); setNotice('')
    try {
      const result = await generateArtifact(documentId, tab, mode, abort.signal, tab === 'quiz' ? { questionTypes, questionCount: 12 } : undefined)
      if (!abort.signal.aborted) {
        setArtifacts(current => tab === 'quiz' ? [result.artifact, ...current.filter(a => a.id !== result.artifact.id && !sameQuiz(a, questionTypes))]
          : [...current.filter(a => a.id !== result.artifact.id), result.artifact])
        setLegacyId(null); setNotice(result.cached ? 'Loaded saved artifact.' : 'Artifact generated and saved for this session.')
      }
    } catch (e) { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : 'Unable to generate this artifact.') }
    finally { if (!abort.signal.aborted) setGenerating(false) }
  }
  const viewSource = async (chunk: string) => {
    sourceController.current?.abort(); const abort = new AbortController(); sourceController.current = abort
    setSource(null); setSourceLoading(true); setError('')
    try { const result = await getSource(documentId, chunk, abort.signal); if (!abort.signal.aborted) setSource(result) }
    catch (e) { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : 'Source unavailable.') }
    finally { if (!abort.signal.aborted) setSourceLoading(false) }
  }
  const content = artifact?.content
  const empty = content && (tab === 'quiz' ? !content.questions?.length : !Object.values(content).some(value => Array.isArray(value) && value.length > 0))
  return <section aria-label="Knowledge Tools" className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
    <div className="mx-auto max-w-4xl space-y-5">
      <div><h2 className="break-words font-display text-xl">{title}</h2><p className="mt-2 text-sm text-ink-soft">Knowledge Tools · Entire Document</p><p className="mt-1 text-xs text-ink-soft">Source-based concepts and practice materials. Saved until this document’s session ends.</p></div>
      <div role="tablist" aria-label="Artifact types" className="flex flex-wrap gap-2">{tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} aria-controls="knowledge-content" className={tab === id ? toolButton.replace('hover:bg-panel', 'hover:bg-brand') + ' bg-brand text-paper' : toolButton} disabled={generating} onClick={() => { setTab(id); setSource(null); setNotice('') }}>{label}</button>)}</div>
      {tab === 'summary' && <label className="block text-sm">Summary length <select className="ml-2 border border-line bg-paper p-2" disabled={generating} value={mode} onChange={e => setMode(e.target.value)}><option value="quick">Quick · up to 5 sentences</option><option value="detailed">Detailed · up to 12 sentences</option></select></label>}
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
      {error && <div role="alert" className="border border-line p-3"><p>{error}</p><button className={toolButton + ' mt-2'} disabled={loading || generating} onClick={() => { setLoading(true); setError(''); load() }}>Retry loading</button></div>}
      {loading ? <p role="status">Loading saved artifacts…</p> : <div role="tabpanel" id="knowledge-content" aria-label={tabs.find(t => t[0] === tab)?.[1]}>
        {!artifact && <div className="border border-line bg-panel p-5"><p>{tab === 'quiz' ? 'No saved quiz for these question types yet.' : `No saved ${tabs.find(t => t[0] === tab)?.[1].toLowerCase()} yet.`}</p>{tab !== 'quiz' && <button className={toolButton + ' mt-4'} disabled={generating} onClick={generate}>{generating ? 'Generating…' : 'Generate'}</button>}</div>}
        {notice && <p role="status" className="mb-3 text-sm text-ink-soft">{notice}</p>}
        {artifact?.analysis?.sampled && <p className="mb-3 text-sm text-ink-soft">This large document was sampled across its chunks. Some topics may be absent.</p>}
        {tab === 'quiz' && content?.messages?.map(message => <p key={message} role="status" className="mb-3 text-sm text-ink-soft">{message}</p>)}
        {empty && <p role="status" className="border border-line p-5">{tab === 'flashcards' ? 'Not enough definition-style content was found in this document to create reliable flashcards or cloze cards.' : 'Not enough reliable source content was found for this artifact.'}</p>}
        {content?.concepts && !empty && <ul className="grid gap-3 sm:grid-cols-2">{content.concepts.map(c => <li key={c.id} className="border border-line bg-panel p-4"><p className="font-medium">{c.label}</p><SourceLink source={c} onSource={viewSource} /></li>)}</ul>}
        {content?.sentences && !empty && <ol className="space-y-4">{content.sentences.map((s, i) => <li key={i} className="border border-line p-4"><p className="whitespace-pre-line leading-relaxed">{s.text}</p><SourceLink source={s} onSource={viewSource} /></li>)}</ol>}
        {content?.cards && !empty && <Flashcards key={artifact?.id} cards={content.cards} onSource={viewSource} />}
        {content?.nodes && !empty && <KnowledgeMap nodes={content.nodes} edges={content.edges || []} onSource={viewSource} />}
        {content?.questions && !empty && <Quiz key={artifact?.id} questions={content.questions} onSource={viewSource} />}
      </div>}
      {sourceLoading && <p role="status">Loading source…</p>}
      {source && <aside aria-label="Source excerpt" className="border border-line bg-panel p-4"><div className="flex items-start justify-between gap-3"><h3 className="break-words font-medium">{source.filename} · {source.pageStart ? `Page ${source.pageStart}` : 'Page unknown'}</h3><button className={toolButton} onClick={() => setSource(null)}>Close source</button></div><p className="mt-2 break-all text-xs text-ink-soft">{source.chunkId}</p><blockquote className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed">{source.text}</blockquote></aside>}
    </div>
  </section>
}
