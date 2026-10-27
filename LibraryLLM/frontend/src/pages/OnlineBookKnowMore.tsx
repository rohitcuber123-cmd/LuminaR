import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { LuminarSelect } from '../components/LuminarSelect'
import { KnowledgeTools } from '../components/knowledge/KnowledgeTools'
import { RAGAnswer } from '../components/rag/RAGAnswer'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { useAuthStore } from '../store/useAuthStore'
import { useProductContext } from '../hooks/useProductContext'
import { useAssistantPageContext } from '../hooks/useAssistantPageContext'
import { ApiError } from '../lib/api'
import { askAsset, fetchAsset, type LibraryAsset, type AssetRAGResult } from '../lib/libraryAssets'
import { libraryReadOnlinePath } from '../lib/libraryBookCapabilities'
import { libraryBookPath } from '../lib/libraryWorkspace'

/** Online copies use library asset access, independently of physical loans. */
export function OnlineBookKnowMore({ libraryId, assetId, bookId }: { libraryId: string; assetId: string; bookId: string }) {
  const token = useAuthStore(state => state.token), product = useProductContext()
  const target = useMemo(() => ({ libraryId, assetId }), [libraryId, assetId])
  const [asset, setAsset] = useState<LibraryAsset | null>(null), [assetError, setAssetError] = useState('')
  const [workspace, setWorkspace] = useState<'ask' | 'knowledge'>('ask')
  const [question, setQuestion] = useState(''), [depth, setDepth] = useState('normal')
  const [answer, setAnswer] = useState<AssetRAGResult | null>(null), [error, setError] = useState(''), [asking, setAsking] = useState(false)
  const request = useRef<AbortController | null>(null)
  const staff = product.kind === 'STAFF_LIBRARY' && product.staffLibraryId === libraryId
  useAssistantPageContext(asset ? { document_id: `library:${libraryId}:asset:${assetId}` } : {})

  useEffect(() => {
    let alive = true, controller: AbortController | undefined
    async function load() {
      controller?.abort(); controller = new AbortController()
      try {
        const row = await fetchAsset(libraryId, assetId, controller.signal)
        if (!bookId || row.library_book_id !== bookId) throw new Error('This online copy is no longer linked to the selected book.')
        if (row.status !== 'READY') throw new Error('This online copy is not ready for Know More.')
        if (!staff && row.visibility !== 'MEMBERS') throw new Error('This online copy is not available to library members.')
        if (alive && token === useAuthStore.getState().token) { setAsset(row); setAssetError('') }
      } catch (reason) {
        if (alive && !(reason instanceof DOMException && reason.name === 'AbortError')) {
          request.current?.abort(); setAsset(null); setAnswer(null)
          setAssetError(reason instanceof Error ? reason.message : 'Unable to access this online copy.')
        }
      }
    }
    if (token) void load()
    window.addEventListener('focus', load)
    return () => { alive = false; controller?.abort(); request.current?.abort(); window.removeEventListener('focus', load) }
  }, [libraryId, assetId, bookId, token, staff])

  async function ask(event: FormEvent) {
    event.preventDefault()
    if (!asset || asking || !question.trim()) return
    const controller = new AbortController(); request.current = controller
    setAsking(true); setError(''); setAnswer(null)
    try {
      const result = await askAsset(target, question.trim(), depth, controller.signal)
      if (!controller.signal.aborted) setAnswer(result)
    } catch (reason) {
      if (!controller.signal.aborted) {
        const message = reason instanceof Error ? reason.message : 'Unable to answer this question. Try again.'
        if (reason instanceof ApiError && [401, 403, 404].includes(reason.status)) { setAsset(null); setAssetError(message) }
        else setError(message)
      }
    } finally { if (!controller.signal.aborted) setAsking(false) }
  }

  return <section className="global-page product-catalogue w-full min-h-0 flex-1 overflow-y-auto" aria-label="Online book Know More">
    <Link className="book-title-link" to={libraryBookPath(libraryId,bookId,staff)}>← Back to book</Link>
    {!token ? <StatePanel title="Sign in to use Know More" kind="error" /> : assetError ?
      <StatePanel title="Online copy unavailable" kind="error">{assetError}</StatePanel> : !asset ?
      <StatePanel title="Loading online book…" kind="loading" /> : <>
      <PageHeading eyebrow="Know More" title={asset.title} description="Ask questions and study this book’s online copy." actions={<>
        <Link className="ui-button ui-secondary" to={libraryReadOnlinePath(libraryId,bookId,assetId,staff)}>Read Online</Link>
        <Link className="ui-button ui-secondary" to={product.personalPath('/llm')}>Other sources</Link>
      </>} />
      <nav aria-label="Book workspace" className="ui-actions mb-6">
        <button className={`ui-button${workspace === 'ask' ? '' : ' ui-secondary'}`} aria-pressed={workspace === 'ask'} onClick={() => setWorkspace('ask')}>Ask Book</button>
        <button className={`ui-button${workspace === 'knowledge' ? '' : ' ui-secondary'}`} aria-pressed={workspace === 'knowledge'} onClick={() => setWorkspace('knowledge')}>Knowledge Tools</button>
      </nav>
      {workspace === 'knowledge' ? <KnowledgeTools documentId={assetId} title={asset.title} libraryAsset={target} /> : <>
        <form className="ui-card grid gap-4" onSubmit={event => void ask(event)}>
          <label htmlFor="online-book-question">Question<textarea id="online-book-question" className="block w-full mt-2" rows={3} maxLength={4000} required value={question} onChange={event => setQuestion(event.target.value)} placeholder="Ask about this book…" /></label>
          <div className="ui-actions"><label htmlFor="online-book-depth">Answer depth<LuminarSelect id="online-book-depth" value={depth} onChange={event => setDepth(event.target.value)}>
            <option value="concise">Concise</option><option value="normal">Normal</option><option value="detailed">Detailed</option><option value="comprehensive">Comprehensive</option>
          </LuminarSelect></label><button className="ui-button" disabled={asking || !question.trim()}>{asking ? 'Answering…' : 'Ask'}</button></div>
        </form>
        {error && <p role="alert" className="my-4">{error}</p>}
        {asking && <p role="status" className="my-4">Reading the online copy…</p>}
        {answer && <section className="ui-card mt-6" aria-label="Book answer"><RAGAnswer text={answer.answer || 'There is not enough information in this online copy to answer reliably.'} />
          {!!answer.sources?.length && <details className="mt-4"><summary>Sources</summary><ul>{answer.sources.map((source,index) => <li key={source.chunk_id || index}>{source.filename || asset.original_filename}{source.page != null && ` · Page ${source.page}`}</li>)}</ul></details>}
        </section>}
      </>}
    </>}
  </section>
}
