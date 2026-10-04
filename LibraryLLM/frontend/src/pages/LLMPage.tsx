import {
  useEffect,
  useCallback,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type RefObject,
} from 'react'
import { useSearchParams } from 'react-router-dom'

import {
  BookOpen,
  FileText,
  Loader2,
  Menu,
  Plus,
  Send,
  Sparkles,
  X,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react'

import {
  uploadRAGDocument,
  askRAG,
  getRAGDocuments,
  getKnowMoreBooks,
  BORROW_STATE_CHANGED,
  type KnowMoreBook,
  type RAGDocument,
  type RAGResponse,
} from '@/lib/api'
import { DeviceDocuments } from '@/components/DeviceDocuments'
import { useDeviceDocuments } from '@/hooks/useDeviceDocuments'
import { useAuthStore } from '@/store/useAuthStore'
import { useAssistantPageContext } from '@/hooks/useAssistantPageContext'


type Message = {
  id: number
  role: 'user' | 'assistant'
  text: string
  sources?: RAGResponse['sources']
  verdict?: string
}


type ComposerProps = {
  welcome?: boolean

  input: string

  setInput: (
    value: string
  ) => void

  uploading: boolean

  fileRef:
    RefObject<HTMLInputElement | null>

  handleFile: (
    event: ChangeEvent<HTMLInputElement>
  ) => void

  handleKeyDown: (
    event: KeyboardEvent<HTMLTextAreaElement>
  ) => void

  sendMessage: () => void

  asking: boolean

  depth: string

  setDepth: (
    value: string
  ) => void
}


const QUICK_PROMPTS = [
  {
    label: 'Summarize',
    prompt: 'Summarize this document for me.',
  },
  {
    label: 'Explain',
    prompt: 'Explain the main concepts in simple terms.',
  },
  {
    label: 'Questions',
    prompt: 'Generate important questions from this document.',
  },
  {
    label: 'Revision',
    prompt: 'Create revision notes from this document.',
  },
]


/*
============================================================
COMPOSER

Keep this component OUTSIDE LLMPage.

This prevents the textarea from being recreated whenever
the input state changes and therefore prevents focus loss.
============================================================
*/

function Composer({
  welcome = false,

  input,
  setInput,

  uploading,

  fileRef,

  handleFile,
  handleKeyDown,

  sendMessage,

  asking,

  depth,
  setDepth,
}: ComposerProps) {

  return (
    <div
      className={`
        w-full

        ${
          welcome
            ? 'mt-8 mb-8'
            : ''
        }
      `}
    >


      {/* =====================================================
          QUESTION BOX
      ===================================================== */}

      <div
        className="
          border
          border-line
          bg-panel
          transition
          duration-200
          focus-within:border-brand
        "
      >

        <textarea
          value={input}

          onChange={(event) =>
            setInput(
              event.target.value
            )
          }

          onKeyDown={handleKeyDown}

          rows={1}

          placeholder="Ask a question about your document..."

          className="
            max-h-24
            min-h-[62px]
            w-full
            resize-none
            bg-transparent
            px-5
            py-4
            text-[0.86rem]
            leading-5
            text-ink
            outline-none
            placeholder:text-ink-soft/60
          "
        />


        {/* =================================================
            INPUT ACTION BAR
        ================================================= */}

        <div
          className="
            flex
            items-center
            justify-between
            border-t
            border-line
            px-3
            py-2.5
          "
        >

          <input
            ref={fileRef}

            type="file"

            className="hidden"

            accept=".pdf"

            onChange={handleFile}
          />


          {/* ===============================================
              ADD DOCUMENT
          =============================================== */}

          <button
            onClick={() =>
              fileRef.current?.click()
            }

            disabled={uploading}

            className="
              flex
              items-center
              gap-2
              px-2
              py-2
              text-ink-soft
              transition
              duration-200
              hover:text-brand
              disabled:opacity-40
              disabled:cursor-not-allowed
            "
          >

            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}

            <span
              className="
                font-display
                text-[0.62rem]
                uppercase
                tracking-wide
              "
            >
              {uploading
                ? 'Uploading...'
                : 'Add Document'
              }
            </span>

          </button>



          {/* ===============================================
              RESPONSE STYLE + ASK
          =============================================== */}

          <div
            className="
              flex
              items-center
              gap-3
            "
          >

            <select
              value={depth}

              onChange={(e) =>
                setDepth(e.target.value)
              }

              aria-label="Response detail level"

              className="
                h-9
                cursor-pointer
                border
                border-line
                bg-paper
                px-3
                font-display
                text-[0.62rem]
                uppercase
                tracking-wide
                text-ink-soft
                outline-none
                transition
                duration-200
                hover:border-brand
                hover:text-brand
                focus:border-brand
              "
            >

              <option value="concise">
                Concise
              </option>

              <option value="normal">
                Normal
              </option>

              <option value="detailed">
                Detailed
              </option>

              <option value="comprehensive">
                Comprehensive
              </option>

            </select>


            {/* ASK BUTTON */}

            <button
              onClick={sendMessage}

              disabled={
                !input.trim() || asking
              }

              className="
                flex
                h-9
                items-center
                gap-2
                bg-brand
                px-5
                text-paper
                transition
                duration-200
                hover:opacity-90
                disabled:cursor-not-allowed
                disabled:opacity-30
              "
            >

              {asking ? (
                <Loader2
                  className="h-3.5 w-3.5 animate-spin"
                />
              ) : (
                <>
                  <span
                    className="
                      hidden
                      font-display
                      text-[0.62rem]
                      uppercase
                      tracking-wide
                      sm:inline
                    "
                  >
                    Ask
                  </span>

                  <Send className="h-3.5 w-3.5" />
                </>
              )}

            </button>

          </div>

        </div>

      </div>

    </div>
  )
}



export function LLMPage() {

  const [searchParams, setSearchParams] = useSearchParams()
  const bookIdFromUrl = searchParams.get('book')

  const [sidebarOpen, setSidebarOpen] =
    useState(true)

  const [input, setInput] =
    useState('')

  const [depth, setDepth] =
    useState('normal')

  const [messages, setMessages] =
    useState<Message[]>([])

  const fileRef =
    useRef<HTMLInputElement>(null)

  const messagesEndRef =
    useRef<HTMLDivElement>(null)


  // ========================================================
  // RAG STATE
  // ========================================================

  const [documents, setDocuments] =
    useState<RAGDocument[]>([])

  const [myKnowMoreBooks, setMyKnowMoreBooks] =
    useState<KnowMoreBook[]>([])
  const token = useAuthStore(state => state.token)
  const device = useDeviceDocuments(token)
  const [keepOnDevice, setKeepOnDevice] = useState(false)
  const [previousFile, setPreviousFile] = useState<{ file: File; cacheId: string } | null>(null)
  const booksRequestId = useRef(0)
  const selectedBookId = useRef<string | null>(null)
  const conversationRevision = useRef(0)
  const [bookAccessMessage, setBookAccessMessage] = useState('')

  const [booksLoading, setBooksLoading] =
    useState(true)

  const [booksError, setBooksError] =
    useState(false)

  const [selectedDocumentId, setSelectedDocumentId] =
    useState<string | null>(null)

  useEffect(() => {
    const clear = () => {
      ++conversationRevision.current
      setDocuments([]); setMessages([]); setSelectedDocumentId(null); setPreviousFile(null); setKeepOnDevice(false)
      selectedBookId.current = null
    }
    clear()
    window.addEventListener('luminar-documents-cleared', clear)
    return () => { window.removeEventListener('luminar-documents-cleared', clear) }
  }, [token])

  useAssistantPageContext(selectedDocumentId
    ? selectedBookId.current === selectedDocumentId ? { work_id: selectedDocumentId } : { document_id: selectedDocumentId }
    : {})

  const selectedDocName =
    documents.find((d) => d.document_id === selectedDocumentId)?.filename ||
    myKnowMoreBooks.find((b) => b.work_id === selectedDocumentId)?.title ||
    selectedDocumentId

  const [uploading, setUploading] =
    useState(false)

  const [uploadError, setUploadError] =
    useState<string | null>(null)

  const [asking, setAsking] =
    useState(false)

  // ========================================================
  // LOAD DOCUMENTS ON MOUNT
  // ========================================================

  const refreshBooks = useCallback(async () => {
    const requestId = ++booksRequestId.current
    setBooksLoading(true)
    setBooksError(false)
    try {
      const response = token ? await getKnowMoreBooks() : { books: [] }
      if (requestId !== booksRequestId.current) return
      setMyKnowMoreBooks(response.books)
      if (selectedBookId.current && !response.books.some(book => book.work_id === selectedBookId.current)) {
        ++conversationRevision.current
        selectedBookId.current = null
        setSelectedDocumentId(null)
        setMessages([])
        setBookAccessMessage('This book is no longer available for Know More. Check your active loans.')
      }
    } catch {
      if (requestId !== booksRequestId.current) return
      setMyKnowMoreBooks([])
      setBooksError(true)
      if (selectedBookId.current) {
        ++conversationRevision.current
        selectedBookId.current = null
        setSelectedDocumentId(null)
        setMessages([])
      }
    } finally {
      if (requestId === booksRequestId.current) setBooksLoading(false)
    }
  }, [token])

  useEffect(() => {
    void Promise.all([refreshDocuments(), refreshBooks()])
    const refresh = () => { void refreshBooks() }
    const onStorage = (event: StorageEvent) => {
      if (event.key === BORROW_STATE_CHANGED) refresh()
    }
    window.addEventListener(BORROW_STATE_CHANGED, refresh)
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', refresh)
    const interval = window.setInterval(refresh, 60000)
    return () => {
      ++booksRequestId.current
      window.removeEventListener(BORROW_STATE_CHANGED, refresh)
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', refresh)
      window.clearInterval(interval)
    }
  }, [refreshBooks])

  useEffect(() => {
    if (!bookIdFromUrl || booksLoading) return
    if (!booksError && myKnowMoreBooks.some(book => book.work_id === bookIdFromUrl)) {
      if (selectedBookId.current !== bookIdFromUrl) {
        ++conversationRevision.current
        setMessages([])
      }
      selectedBookId.current = bookIdFromUrl
      setSelectedDocumentId(bookIdFromUrl)
      setBookAccessMessage('')
    } else {
      if (selectedBookId.current || selectedDocumentId) {
        ++conversationRevision.current
        setMessages([])
      }
      selectedBookId.current = null
      setSelectedDocumentId(null)
      setBookAccessMessage('This book is not available for Know More. Sign in and borrow a RAG-enabled book.')
    }
  }, [bookIdFromUrl, booksLoading, booksError, myKnowMoreBooks, selectedDocumentId])


  // ========================================================
  // AUTO-SCROLL
  // ========================================================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView(
      { behavior: 'smooth' }
    )
  }, [messages])


  // ========================================================
  // REFRESH DOCUMENTS
  // ========================================================

  async function refreshDocuments() {
    try {

      const listToken = useAuthStore.getState().token
      const response =
        await getRAGDocuments()
      if (listToken !== useAuthStore.getState().token) return

      setDocuments(
        response.documents || []
      )

    } catch {
      // Silent — documents list is optional
    }
  }


  function selectSource(id: string | null, isBook = false) {
    ++conversationRevision.current
    selectedBookId.current = isBook ? id : null
    setSelectedDocumentId(id)
    setMessages([])
    setBookAccessMessage('')
    const next = new URLSearchParams(searchParams)
    if (isBook && id) next.set('book', id)
    else next.delete('book')
    setSearchParams(next, { replace: true })
  }


  // ========================================================
  // NEW CHAT
  // ========================================================

  function newChat() {
    ++conversationRevision.current

    setMessages([])

    setInput('')

    setSelectedDocumentId(null)
    selectedBookId.current = null
    setBookAccessMessage('')

    setUploadError(null)

    if (searchParams.has('book')) {
      searchParams.delete('book')
      setSearchParams(searchParams)
    }
  }


  // ========================================================
  // FILE UPLOAD
  // ========================================================

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]
    event.target.value = ''
    if (!selected) return
    if (device.enabled && selected.size <= 64 * 1024 * 1024) {
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await selected.arrayBuffer()))].map(b => b.toString(16).padStart(2, '0')).join('')
      const existing = device.copies.find(copy => !copy.error && copy.descriptor?.document_sha256 === hash)
      if (existing) { setPreviousFile({ file: selected, cacheId: existing.record.cache_id }); return }
    }
    await processFile(selected)
  }

  async function processFile(selected: File, oldCacheId?: string) {
    const uploadToken = token
    setPreviousFile(null)
    setUploading(true)
    setUploadError(null)

    try {

      const result: any =
        await uploadRAGDocument(
          selected
        )

      if (uploadToken !== useAuthStore.getState().token) return
      const documentId =
        result?.document?.document_id

      if (documentId) {
        selectSource(documentId)
      }

      await refreshDocuments()
      if (documentId && keepOnDevice && device.enabled) void device.save(documentId)
      else if (documentId && oldCacheId) await device.removeCopy(oldCacheId)

    } catch (error: any) {

      setUploadError(
        error?.message ||
        'Upload failed. Please try again.'
      )

    } finally {

      setUploading(false)
    }
  }


  // ========================================================
  // SEND MESSAGE (REAL RAG)
  // ========================================================

  async function sendMessage() {

    const question =
      input.trim()

    if (!question || asking) return
    if (bookIdFromUrl && (booksLoading || selectedBookId.current !== bookIdFromUrl)) {
      setBookAccessMessage('Select an eligible borrowed book, a document, or start a new session.')
      return
    }


    const userMessage: Message = {

      id:
        Date.now(),

      role:
        'user',

      text:
        question,
    }


    setMessages(
      (previous) => [

        ...previous,

        userMessage,

      ]
    )


    setInput('')

    setAsking(true)
    const requestRevision = conversationRevision.current

    try {

      const result = await askRAG(
        question,
        depth as
          | 'concise'
          | 'normal'
          | 'detailed'
          | 'comprehensive',
        selectedDocumentId,
        selectedBookId.current === selectedDocumentId,
      )
      if (requestRevision !== conversationRevision.current) return


      // Determine display text

      let answerText =
        result.answer || ''

      // Handle unsupported premise
      // with a user-friendly message

      if (
        result.verdict ===
        'NOT_SUPPORTED'
        && !answerText
      ) {
        answerText =
          "There's not enough information " +
          "in the available documents to " +
          "answer that reliably."
      }


      const assistantMessage:
        Message = {

        id:
          Date.now() + 1,

        role:
          'assistant',

        text:
          answerText,

        sources:
          result.sources,

        verdict:
          result.verdict,
      }


      setMessages(
        (previous) => [

          ...previous,

          assistantMessage,

        ]
      )


    } catch (error: any) {

      if (requestRevision !== conversationRevision.current) return

      const errorMessage =
        error?.message ||
        'Failed to get a response. ' +
        'Please try again.'

      const errorMsg: Message = {

        id:
          Date.now() + 1,

        role:
          'assistant',

        text:
          errorMessage,
      }

      setMessages(
        (previous) => [

          ...previous,

          errorMsg,

        ]
      )

    } finally {

      setAsking(false)
    }
  }


  // ========================================================
  // KEYBOARD
  // ========================================================

  function handleKeyDown(
    event:
      KeyboardEvent<HTMLTextAreaElement>
  ) {

    if (
      event.key === 'Enter' &&
      !event.shiftKey
    ) {

      event.preventDefault()

      sendMessage()
    }
  }



  return (

    <div
      className="
        flex
        h-[calc(100dvh-72px)]
        max-h-[calc(100dvh-72px)]
        overflow-hidden
        bg-paper
        text-ink
      "
    >

      {/* =====================================================
          SIDEBAR
      ===================================================== */}

      <aside
        className={`
          ${
            sidebarOpen
              ? 'w-[270px]'
              : 'w-0'
          }

          h-full
          shrink-0
          overflow-hidden
          border-r
          border-line
          bg-panel
          transition-all
          duration-300
        `}
      >

        <div
          className="
            flex
            h-full
            min-h-0
            flex-col
          "
        >

          {/* =================================================
              TITLE
          ================================================= */}

          <div
            className="
              shrink-0
              border-b
              border-line
              px-5
              py-4
            "
          >

            <p
              className="
                font-display
                text-[0.65rem]
                uppercase
                tracking-[0.18em]
                text-brand
              "
            >
              Know More
            </p>

          </div>



          {/* =================================================
              NEW SESSION
          ================================================= */}

          <div
            className="
              shrink-0
              p-4
            "
          >

            <button
              onClick={newChat}

              className="
                flex
                w-full
                items-center
                gap-3
                border
                border-line
                bg-paper
                px-4
                py-3
                text-left
                transition
                hover:border-brand
                hover:text-brand
              "
            >

              <Plus
                className="h-4 w-4"
              />


              <span
                className="
                  font-display
                  text-[0.72rem]
                  uppercase
                  tracking-wide
                "
              >
                New Session
              </span>

            </button>

          </div>



          {/* =================================================
              DOCUMENTS & BOOKS
          ================================================= */}

          <div
            className="
              min-h-0
              flex-1
              overflow-y-auto
              px-4
              pt-2
              pb-4
            "
          >

            <DeviceDocuments documents={documents} selectedId={selectedDocumentId} select={selectSource}
              reload={refreshDocuments} device={device} keep={keepOnDevice} setKeep={setKeepOnDevice} />
            {previousFile && <div role="dialog" aria-label="Previously processed document" className="mt-3 border border-line p-3 text-xs">
              <p>You've processed this document on this device before.</p>
              <button className="mt-2 block text-brand" disabled={!!device.busy} onClick={async () => {
                const doc = await device.restore(previousFile.cacheId)
                if (doc) { setPreviousFile(null); await refreshDocuments(); selectSource(doc.document_id) }
              }}>Restore cached version</button>
              <button className="mt-2 block text-brand" onClick={() => void processFile(previousFile.file, previousFile.cacheId)}>Process again</button>
            </div>}

            {/* BOOKS */}
            <div className="mt-8">
              <p
                className="
                  mb-3
                  px-2
                  font-display
                  text-[0.62rem]
                  uppercase
                  tracking-[0.16em]
                  text-ink-soft
                "
              >
                MY BORROWED BOOKS
              </p>
              
              {booksLoading ? (
                <div className="px-2 py-3 flex items-center justify-center">
                  <Loader2 className="h-4 w-4 animate-spin text-ink-soft" />
                </div>
              ) : booksError ? (
                <p className="px-2 text-[0.72rem] text-red-500">
                  Unable to load your borrowed books.
                </p>
              ) : myKnowMoreBooks.length === 0 ? (
                <p className="px-2 text-[0.72rem] text-ink-soft/60">
                  No borrowed books are available for Know More yet.
                  <br /><br />
                  Borrow a supported readable book to ask questions about it.
                </p>
              ) : (
                <div className="space-y-1">
                  {myKnowMoreBooks.map((book) => (
                    <button
                      key={book.work_id}
                      onClick={() =>
                        selectSource(
                          selectedDocumentId === book.work_id
                            ? null
                            : book.work_id,
                          true
                        )
                      }
                      className={`
                        flex
                        w-full
                        items-center
                        gap-3
                        px-2
                        py-2.5
                        text-left
                        text-[0.8rem]
                        transition
                        ${
                          selectedDocumentId === book.work_id
                            ? 'bg-paper text-brand border-l-2 border-brand'
                            : 'text-ink-soft hover:bg-paper hover:text-ink'
                        }
                      `}
                    >
                      <BookOpen className="h-3.5 w-3.5 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <span className="block truncate text-[0.76rem]">
                          {book.title}
                        </span>
                        <span className="block truncate text-[0.6rem] text-ink-soft/60">
                          {book.authors.join(', ')}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

          </div>



          {/* =================================================
              SIDEBAR FOOTER
          ================================================= */}

          <div
            className="
              shrink-0
              border-t
              border-line
              p-4
            "
          >

            <div
              className="
                flex
                items-center
                gap-3
              "
            >

              <div
                className="
                  flex
                  h-9
                  w-9
                  items-center
                  justify-center
                  bg-brand
                  text-paper
                "
              >

                <BookOpen
                  className="h-4 w-4"
                />

              </div>


              <div>

                <p
                  className="
                    font-display
                    text-[0.7rem]
                    uppercase
                    tracking-wide
                  "
                >
                  Know More
                </p>


                <p
                  className="
                    mt-0.5
                    text-[0.66rem]
                    text-ink-soft
                  "
                >
                  Document Intelligence
                </p>

              </div>

            </div>

          </div>

        </div>

      </aside>



      {/* =====================================================
          MAIN WORKSPACE
      ===================================================== */}

      <main
        className="
          flex
          min-h-0
          min-w-0
          flex-1
          flex-col
          overflow-hidden
          bg-paper
        "
      >

        {bookAccessMessage && <p role="status" className="border-b border-line bg-panel px-5 py-3 text-sm text-ink-soft">{bookAccessMessage}</p>}
        {/* =================================================
            TOP BAR
        ================================================= */}

        <div
          className="
            flex
            h-[54px]
            shrink-0
            items-center
            justify-between
            border-b
            border-line
            px-5
          "
        >

          <div
            className="
              flex
              items-center
              gap-3
            "
          >

            <button
              onClick={() =>
                setSidebarOpen(
                  (value) => !value
                )
              }

              aria-label="Toggle sidebar"

              className="
                flex
                h-8
                w-8
                items-center
                justify-center
                text-ink-soft
                transition
                hover:bg-panel
                hover:text-brand
              "
            >

              <Menu
                className="h-4 w-4"
              />

            </button>


            <h1
              className="
                font-display
                text-[0.88rem]
                uppercase
                tracking-wide
              "
            >
              Know More
            </h1>

          </div>


          <div
            className="
              flex
              items-center
              gap-3
            "
          >

            {/* SELECTED DOCUMENT INDICATOR */}

            {selectedDocumentId && (

              <div
                className="
                  hidden
                  items-center
                  gap-2
                  md:flex
                "
              >

                <FileText
                  className="
                    h-3.5
                    w-3.5
                    text-brand
                  "
                />

                <span
                  className="
                    max-w-[200px]
                    truncate
                    text-[0.65rem]
                    uppercase
                    tracking-[0.08em]
                    text-ink-soft
                  "
                >
                  {selectedDocName}
                </span>

                <button
                  onClick={() =>
                    selectSource(
                      null
                    )
                  }

                  className="
                    text-ink-soft
                    transition
                    hover:text-brand
                  "
                >
                  <X className="h-3 w-3" />
                </button>

              </div>

            )}


            {!selectedDocumentId && (

              <div
                className="
                  hidden
                  items-center
                  gap-2
                  md:flex
                "
              >

                <span
                  className="
                    h-1.5
                    w-1.5
                    rounded-full
                    bg-brand
                  "
                />

                <span
                  className="
                    text-[0.65rem]
                    uppercase
                    tracking-[0.12em]
                    text-ink-soft
                  "
                >
                  All Documents
                </span>

              </div>

            )}

          </div>

        </div>



        {/* =====================================================
            UPLOAD ERROR
        ===================================================== */}

        {uploadError && (

          <div
            className="
              mx-5
              mt-3
              flex
              items-center
              gap-3
              border
              border-red-200
              bg-red-50
              px-4
              py-3
              text-[0.78rem]
              text-red-700
              dark:border-red-800
              dark:bg-red-950/30
              dark:text-red-300
            "
          >

            <AlertTriangle
              className="h-4 w-4 shrink-0"
            />

            <span className="flex-1">
              {uploadError}
            </span>

            <button
              onClick={() =>
                setUploadError(null)
              }

              className="
                shrink-0
                text-red-400
                transition
                hover:text-red-600
              "
            >
              <X className="h-3.5 w-3.5" />
            </button>

          </div>

        )}


        {/* =====================================================
            WELCOME STATE
        ===================================================== */}

        {messages.length === 0 ? (

          <div
            className="
              min-h-0
              flex-1
              overflow-hidden
              px-6
              pt-4
              pb-4
            "
          >

            <div
              className="
                mx-auto
                flex
                h-full
                w-full
                max-w-[820px]
                flex-col
                justify-center
              "
            >

              {/* ICON */}

              <div
                className="
                  mb-3
                  flex
                  justify-center
                "
              >

                <div
                  className="
                    flex
                    h-9
                    w-9
                    items-center
                    justify-center
                    border
                    border-brand
                    text-brand
                  "
                >

                  <Sparkles
                    className="h-4 w-4"
                  />

                </div>

              </div>


              {/* LABEL */}

              <p
                className="
                  mb-2
                  text-center
                  font-display
                  text-[0.62rem]
                  uppercase
                  tracking-[0.18em]
                  text-brand
                "
              >
                LuminaR Document Intelligence
              </p>


              {/* TITLE */}

              <h2
                className="
                  mx-auto
                  max-w-[640px]
                  text-center
                  font-display
                  text-[2.15rem]
                  uppercase
                  leading-[1.02]
                  tracking-tight
                  md:text-[2.35rem]
                "
              >

                Study your documents

                <br />

                with intelligence.

              </h2>


              {/* DESCRIPTION */}

              <p
                className="
                  mx-auto
                  mt-3
                  max-w-[560px]
                  text-center
                  text-[0.82rem]
                  leading-5
                  text-ink-soft
                "
              >

                Upload lecture notes,
                research papers, reports or
                study material and explore
                them through questions.

              </p>



              {/* =================================================
                  QUICK PROMPTS
              ================================================= */}

              <div
                className="
                  mt-5
                  grid
                  shrink-0
                  gap-px
                  overflow-hidden
                  border
                  border-line
                  bg-line
                  sm:grid-cols-2
                "
              >

                {QUICK_PROMPTS.map(
                  (item, index) => (

                    <button
                      key={item.label}

                      onClick={() =>
                        setInput(
                          item.prompt
                        )
                      }

                      className="
                        group
                        min-h-[82px]
                        bg-paper
                        p-3.5
                        text-left
                        transition
                        hover:bg-panel
                      "
                    >

                      <div
                        className="
                          mb-2
                          flex
                          items-center
                          justify-between
                        "
                      >

                        <span
                          className="
                            font-display
                            text-[0.6rem]
                            uppercase
                            text-brand
                          "
                        >
                          0{index + 1}
                        </span>


                        <span
                          className="
                            text-ink-soft
                            transition
                            group-hover:translate-x-1
                            group-hover:text-brand
                          "
                        >
                          →
                        </span>

                      </div>


                      <h3
                        className="
                          font-display
                          text-[0.8rem]
                          uppercase
                          tracking-wide
                        "
                      >
                        {item.label}
                      </h3>


                      <p
                        className="
                          mt-1
                          text-[0.7rem]
                          leading-4
                          text-ink-soft
                        "
                      >
                        {item.prompt}
                      </p>

                    </button>

                  )
                )}

              </div>



              {/* =================================================
                  QUESTION BOX
              ================================================= */}

              <Composer

                welcome

                input={input}

                setInput={setInput}

                uploading={uploading}

                fileRef={fileRef}

                handleFile={handleFile}

                handleKeyDown={
                  handleKeyDown
                }

                sendMessage={
                  sendMessage
                }

                asking={asking}

                depth={depth}

                setDepth={setDepth}

              />

            </div>

          </div>

        ) : (

          /* =====================================================
              CHAT MODE
          ===================================================== */

          <>

            {/* =================================================
                MESSAGES

                Only this area scrolls.
            ================================================= */}

            <div
              className="
                min-h-0
                flex-1
                overflow-y-auto
                overscroll-contain
              "
            >

              <div
                className="
                  mx-auto
                  max-w-[760px]
                  px-5
                  py-8
                "
              >

                {messages.map(
                  (message) => (

                    <div
                      key={message.id}

                      className="
                        mb-8
                        border-b
                        border-line
                        pb-8
                        last:mb-0
                      "
                    >

                      <div
                        className="
                          mb-4
                          flex
                          items-center
                          gap-3
                        "
                      >

                        <div
                          className={`
                            flex
                            h-8
                            w-8
                            items-center
                            justify-center
                            text-[0.62rem]
                            font-semibold

                            ${
                              message.role ===
                              'assistant'

                                ? 'bg-brand text-paper'

                                : 'border border-line bg-panel text-ink'
                            }
                          `}
                        >

                          {
                            message.role ===
                            'assistant'

                              ? 'LR'

                              : 'YOU'
                          }

                        </div>


                        <span
                          className="
                            font-display
                            text-[0.65rem]
                            uppercase
                            tracking-[0.14em]
                            text-ink-soft
                          "
                        >

                          {
                            message.role ===
                            'assistant'

                              ? 'LuminaR'

                              : 'Your Question'
                          }

                        </span>


                        {/* VERDICT BADGE */}

                        {message.role ===
                          'assistant' &&
                          message.verdict && (

                          <span
                            className={`
                              ml-auto
                              flex
                              items-center
                              gap-1
                              px-2
                              py-0.5
                              text-[0.55rem]
                              font-medium
                              uppercase
                              tracking-wide

                              ${
                                message.verdict ===
                                'NOT_SUPPORTED'
                                  ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400'
                                  : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400'
                              }
                            `}
                          >
                            {message.verdict ===
                              'NOT_SUPPORTED' ? (
                              <AlertTriangle
                                className="h-3 w-3"
                              />
                            ) : (
                              <CheckCircle
                                className="h-3 w-3"
                              />
                            )}

                            {message.verdict ===
                              'NOT_SUPPORTED'
                              ? 'Unsupported'
                              : 'Grounded'
                            }
                          </span>

                        )}

                      </div>


                      <div
                        className="
                          pl-11
                          text-[0.9rem]
                          leading-7
                          text-ink
                          whitespace-pre-wrap
                        "
                      >
                        {message.text}
                      </div>


                      {/* SOURCES */}

                      {message.sources &&
                        message.sources.length > 0 && (

                        <div
                          className="
                            mt-4
                            pl-11
                          "
                        >

                          <p
                            className="
                              mb-2
                              font-display
                              text-[0.58rem]
                              uppercase
                              tracking-[0.14em]
                              text-ink-soft
                            "
                          >
                            Sources
                          </p>

                          <div
                            className="
                              flex
                              flex-wrap
                              gap-2
                            "
                          >

                            {message.sources
                              .slice(0, 5)
                              .map(
                                (source, idx) => (

                                <span
                                  key={idx}

                                  className="
                                    inline-flex
                                    items-center
                                    gap-1.5
                                    border
                                    border-line
                                    bg-panel
                                    px-2.5
                                    py-1
                                    text-[0.65rem]
                                    text-ink-soft
                                  "
                                >

                                  <FileText
                                    className="
                                      h-3
                                      w-3
                                    "
                                  />

                                  {source.title ||
                                    source.filename}

                                  {source.page != null && (
                                    <span
                                      className="
                                        text-ink-soft/60
                                      "
                                    >
                                      p.{source.page}
                                    </span>
                                  )}

                                </span>

                              )
                            )}

                          </div>

                        </div>

                      )}

                    </div>

                  )
                )}

                <div ref={messagesEndRef} />

              </div>

            </div>



            {/* =================================================
                CHAT INPUT AREA
            ================================================= */}

            <div
              className="
                shrink-0
                border-t
                border-line
                bg-paper
                px-5
                pt-4
                pb-6
              "
            >

              <div
                className="
                  mx-auto
                  max-w-[820px]
                "
              >

                <Composer

                  input={input}

                  setInput={setInput}

                  uploading={uploading}

                  fileRef={fileRef}

                  handleFile={
                    handleFile
                  }

                  handleKeyDown={
                    handleKeyDown
                  }

                  sendMessage={
                    sendMessage
                  }

                  asking={asking}

                  depth={depth}

                  setDepth={setDepth}

                />

              </div>

            </div>

          </>

        )}

      </main>

    </div>
  )
}
