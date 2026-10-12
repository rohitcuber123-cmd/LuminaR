import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage,
  sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor, act } = await import('@testing-library/react')
const { KnowledgeTools } = await import('../src/components/knowledge/KnowledgeTools.tsx')
const { Quiz } = await import('../src/components/knowledge/Quiz.tsx')
const { useAuthStore } = await import('../src/store/useAuthStore.ts')
const { getSource } = await import('../src/lib/knowledgeArtifacts.ts')
import type { Artifact } from '../src/lib/knowledgeArtifacts.ts'
import type { ClozeGrade, Question, QuizQuestionType } from '../src/lib/knowledgeArtifacts.ts'
const provenance = { sourceChunkIds: ['c1'], pageStart: 4 }
const cards: Artifact = { id: 'cards', documentId: 'doc1', type: 'FLASHCARDS', options: {}, content: { cards: [
  { id: 'd1', type: 'definition', front: 'What does the document say about paging?', back: 'Paging divides memory into fixed-size pages.', sourceExcerpt: 'Paging divides memory into fixed-size pages.', ...provenance },
  { id: 'c1', type: 'cloze', front: '_____ divides memory into fixed-size pages.', back: 'Paging', sourceExcerpt: 'Paging divides memory into fixed-size pages.', ...provenance },
] } }
let stored: Artifact[], calls: { url: string; method: string }[], originalFetch: typeof fetch, status: number
beforeEach(() => {
  localStorage.setItem('luminar_token', 'session1')
  act(() => useAuthStore.setState({ token: 'session1', isAuthenticated: true }))
  stored = []; calls = []; status = 200; originalFetch = globalThis.fetch
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method || 'GET' })
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer session1')
    if (status !== 200) return new Response(JSON.stringify({ detail: 'sensitive backend diagnostic' }), { status })
    if (String(url).includes('/cloze/')) {
      const itemId=decodeURIComponent(String(url).split('/cloze/')[1].split('/')[0])
      const q=stored.flatMap(a=>a.content.questions || []).find(q=>q.id===itemId)
      assert.ok(q && q.type==='fill_blank')
      return new Response(JSON.stringify({verdict:'CORRECT',canonical_answer:q.correctAnswer,feedback:'Your answer matches the source meaning.',source_pages:[4],source_chunk_ids:['c1']}))
    }
    if (String(url).includes('/sources/')) return new Response(JSON.stringify({ ...provenance, chunkId: 'c1', filename: 'Manual.pdf', text: 'Paging divides memory into fixed-size pages.' }))
    if (init.method === 'POST') { stored = [cards]; return new Response(JSON.stringify({ artifact: cards, cached: false })) }
    return new Response(JSON.stringify({ artifacts: stored }))
  }
})
afterEach(() => { cleanup(); globalThis.fetch = originalFetch })
const mount = () => render(<KnowledgeTools documentId="doc1" title="Manual.pdf" />)

test('card keyboard navigation flips and clamps at deck boundaries', async () => {
  stored=[cards];mount();await screen.findByText('Card 1 of 2')
  await act(async () => {})
  const card=screen.getByLabelText('Flashcard')
  fireEvent.keyDown(card,{key:'ArrowRight'});assert.ok(screen.getByText('Card 2 of 2'))
  fireEvent.keyDown(card,{key:'ArrowRight'});assert.ok(screen.getByText('Card 2 of 2'))
  fireEvent.keyDown(card,{key:' '});assert.ok(screen.getByText('Answer'))
  fireEvent.keyDown(card,{key:'Enter'});assert.ok(screen.getByText('Front'))
  fireEvent.keyDown(card,{key:'ArrowLeft'});assert.ok(screen.getByText('Card 1 of 2'))
})

test('card shortcuts never consume select or button keyboard events', async () => {
  stored=[cards];mount();await screen.findByText('Card 1 of 2')
  fireEvent.keyDown(screen.getByRole('combobox'),{key:'ArrowRight'})
  fireEvent.keyDown(screen.getByRole('button',{name:'Reveal answer'}),{key:' '})
  assert.ok(screen.getByText('Card 1 of 2'));assert.ok(screen.getByText('Front'))
})

test('card filtering resets to the first available card', async () => {
  stored=[cards];mount();await screen.findByText('Card 1 of 2')
  fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'definition'}})
  assert.ok(screen.getByText('Card 1 of 1'))
  assert.ok((screen.getByRole('button',{name:'Next →'}) as HTMLButtonElement).disabled)
})

test('concepts display grounded explanations and page-specific source buttons', async () => {
  stored = [{ id: 'concepts', documentId: 'doc1', type: 'KEY_CONCEPTS', options: {}, content: { concepts: [
    { id: 'window', label: 'Sliding Window', explanation: 'A sender can transmit several frames before acknowledgment.',
      sourceChunkIds: ['page2', 'page7', 'page7duplicate'], pageStart: 2, pageEnd: 7,
      sources: [{ chunkId: 'page2', page: 2 }, { chunkId: 'page7', page: 7 }, { chunkId: 'page7duplicate', page: 7 }] },
  ] } }]
  mount(); await screen.findByRole('button', { name: 'Generate' })
  fireEvent.click(screen.getByRole('tab', { name: 'Key Concepts' }))
  assert.ok(screen.getByText('A sender can transmit several frames before acknowledgment.'))
  assert.equal(screen.getAllByRole('button', { name: 'Page 7' }).length, 1)
  assert.equal(screen.queryByRole('button', { name: 'View source 1' }), null)
  fireEvent.click(screen.getByRole('button', { name: 'Page 7' }))
  await screen.findByRole('complementary', { name: 'Source excerpt' })
  assert.ok(calls.some(c => c.url.endsWith('/sources/page7')))
})

test('structured summary renders supported section headings', async () => {
  stored = [{ id: 'summary', documentId: 'doc1', type: 'EXTRACTIVE_SUMMARY', options: { mode: 'quick' }, content: {
    sections: [{ title: 'Flow control', sentences: [{ text: 'The sender limits frames in transit.', ...provenance }] }],
  } }]
  mount(); await screen.findByRole('button', { name: 'Generate' })
  fireEvent.click(screen.getByRole('tab', { name: 'Summary' }))
  assert.ok(screen.getByRole('heading', { name: 'Flow control' }))
  assert.ok(screen.getByText('The sender limits frames in transit.'))
})

test('busy admission has a safe retry message', async () => {
  mount(); await screen.findByRole('button', { name: 'Generate' })
  status = 429
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  assert.ok(await screen.findByText('A study artifact is already being prepared. Please wait, then retry.'))
  assert.ok(screen.getByRole('button', { name: 'Retry loading' }))
})

test('loading, explicit generation, flip, navigation, type filter and source preview', async () => {
  mount(); assert.ok(screen.getByText('Loading saved artifacts…'))
  fireEvent.click(await screen.findByRole('button', { name: 'Generate' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Reveal answer' }))
  assert.ok(screen.getByText('Paging divides memory into fixed-size pages.'))
  fireEvent.click(screen.getByRole('button', { name: 'Next →' }))
  assert.ok(screen.getByText('_____ divides memory into fixed-size pages.'))
  fireEvent.click(screen.getByRole('button', { name: '← Previous' }))
  fireEvent.change(screen.getByLabelText('Card type'), { target: { value: 'cloze' } })
  assert.ok(screen.getByText('Card 1 of 1'))
  fireEvent.click(screen.getByRole('button', { name: 'View source' }))
  assert.ok(await screen.findByRole('complementary', { name: 'Source excerpt' }))
  assert.equal(calls.filter(c => c.method === 'POST').length, 1)
})

test('reopening uses persisted list and tab changes do not generate', async () => {
  stored = [cards]
  const first = mount()
  await screen.findByRole('button', { name: 'Reveal answer' })
  fireEvent.click(screen.getByRole('tab', { name: 'Key Concepts' }))
  assert.ok(screen.getByRole('button', { name: 'Generate' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Flashcards' }))
  assert.ok(screen.getByRole('button', { name: 'Reveal answer' }))
  first.unmount(); mount()
  await screen.findByRole('button', { name: 'Reveal answer' })
  assert.equal(calls.filter(c => c.method === 'POST').length, 0)
})

test('structured map renders selectable nodes, zoom and reset controls', async () => {
  stored = [{ id: 'map', documentId: 'doc1', type: 'MIND_MAP', options: {}, content: { nodes: [
    { id: 'root', type: 'document', label: 'Manual', sourceChunkIds: [] }, { id: 'paging', type: 'concept', label: 'Paging', ...provenance },
  ], edges: [{ source: 'root', target: 'paging', relation: 'contains' }] } }]
  mount(); await screen.findByRole('button', { name: 'Generate' })
  fireEvent.click(screen.getByRole('tab', { name: 'Mind Map' }))
  assert.ok(screen.getByRole('group', { name: 'Document concept map' }))
  fireEvent.keyDown(screen.getByRole('button', { name: 'Paging' }), { key: 'Enter' })
  assert.ok(screen.getByRole('button', { name: 'View source' }))
  fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))
  fireEvent.click(screen.getByRole('button', { name: 'Reset view' }))
  fireEvent.click(screen.getByRole('button', { name: 'Fullscreen' }))
  const dialog = screen.getByRole('dialog', { name: 'Fullscreen mind map' })
  fireEvent.click(screen.getByRole('button', { name: 'View source' }))
  const excerpt = await screen.findByRole('complementary', { name: 'Source excerpt' })
  assert.ok(dialog.contains(excerpt))
  assert.ok(calls.some(c => c.url.endsWith('/sources/c1')))
  fireEvent.click(screen.getByRole('button', { name: 'Close source' }))
  assert.equal(screen.queryByRole('complementary', { name: 'Source excerpt' }), null)
  fireEvent.keyDown(window, { key: 'Escape' })
  assert.equal(screen.queryByRole('dialog'), null)
})

test('quiz checks answers and reveals source only after submission', async () => {
  stored = [{ id: 'quiz', documentId: 'doc1', type: 'QUIZ', options: {}, content: { questions: [
    { id: 'q1', type: 'fill_blank', question: '_____ divides memory.', correctAnswer: 'Paging', sourceExcerpt: 'Paging divides memory.', ...provenance },
  ] } }]
  mount(); await screen.findByRole('button', { name: 'Generate' })
  fireEvent.click(screen.getByRole('tab', { name: 'Quiz' }))
  fireEvent.click(screen.getByRole('button', { name: 'View previously saved quiz' }))
  assert.equal(screen.queryByText('Paging divides memory.'), null)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'paging' } })
  fireEvent.click(screen.getByRole('button', { name: 'Check answer' }))
  await screen.findByText('✓ Correct'); assert.ok(screen.getByText('Accepted answer: Paging'))
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  assert.equal(screen.queryByText('✓ Correct'), null)
})

const mcq: Question = { id:'mcq1', type:'mcq', question:'Which concept divides memory into pages?',
  options:['Queue','Stack','Paging','Tree'], correctAnswer:'Paging', sourceExcerpt:'Paging divides memory into fixed-size pages.', ...provenance }
const blank: Question = { id:'blank1', type:'fill_blank', question:'_____ stores values in arrival order.',
  correctAnswer:'Queue', sourceExcerpt:'Queue stores values in arrival order.', ...provenance }
const matching: Question = { id:'matching1', type:'matching', question:'Match the concepts with their descriptions.',
  leftItems:[
    {id:'L1',text:'Stack',sourceExcerpt:'Stack removes the most recent value first.',...provenance},
    {id:'L2',text:'Tree',sourceExcerpt:'Tree connects parent and child nodes.',...provenance},
    {id:'L3',text:'Graph',sourceExcerpt:'Graph represents vertices and edges.',...provenance},
  ], rightItems:[{id:'R2',text:'Connects parent and child nodes.'},{id:'R3',text:'Represents vertices and edges.'},{id:'R1',text:'Removes the most recent value first.'}],
  correctMatches:{L1:'R1',L2:'R2',L3:'R3'},sourceExcerpt:'Three source definitions.',...provenance }
const newQuiz = (types: QuizQuestionType[], questions: Question[] = [mcq,blank,matching]): Artifact => ({
  id:'quiz-v2',documentId:'doc1',type:'QUIZ',generatorVersion:'2.0.0',
  options:{questionTypes:types,questionCount:12},content:{questions},
})
const openQuiz = async () => { mount(); await screen.findByRole('tab',{name:'Quiz'}); await waitFor(() => assert.equal(screen.queryByText('Loading saved artifacts…'),null)); fireEvent.click(screen.getByRole('tab',{name:'Quiz'})) }

const clozeResult = (verdict: ClozeGrade['verdict']): ClozeGrade => ({verdict,canonical_answer:'Queue',
  feedback:verdict==='PARTIAL'?'You omitted an important source detail.':'Compare your answer with the source.',source_pages:[4],source_chunk_ids:['c1']})

for (const [verdict,label] of [['CORRECT','✓ Correct'],['PARTIAL','~ Partially correct'],['INCORRECT','× Needs review']] as const) {
  test(`cloze server ${verdict} verdict controls accessible feedback`, async () => {
    let sent='';render(<Quiz questions={[blank]} onSource={()=>{}} onGrade={async (_,answer)=>{sent=answer;return clozeResult(verdict)}} />)
    assert.equal(screen.queryByText('Accepted answer: Queue'),null)
    assert.equal(screen.queryByRole('button',{name:'View source'}),null)
    fireEvent.change(screen.getByRole('textbox'),{target:{value:'my natural answer'}})
    fireEvent.click(screen.getByRole('button',{name:'Check answer'}));await screen.findByText(label)
    assert.equal(sent,'my natural answer');assert.ok(screen.getByText('Your answer: my natural answer'))
    assert.ok(screen.getByRole('status').getAttribute('aria-live')==='polite')
    assert.ok(screen.getByText(`${verdict==='CORRECT'?'Accepted answer':'Expected'}: Queue`))
  })
}

test('cloze input submits with Enter and preserves server result through navigation', async () => {
  let requests=0;render(<Quiz questions={[blank,mcq]} onSource={()=>{}} onGrade={async ()=>{requests++;return clozeResult('PARTIAL')}} />)
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'natural phrase'}})
  fireEvent.keyDown(screen.getByRole('textbox'),{key:'Enter'});await screen.findByText('~ Partially correct')
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));fireEvent.click(screen.getByRole('button',{name:'← Previous'}))
  assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'natural phrase')
  assert.ok(screen.getByText('~ Partially correct'));assert.equal(requests,1)
})

test('cloze try again clears only the current response and retains mixed quiz scoring', async () => {
  render(<Quiz questions={[mcq,blank,matching]} onSource={()=>{}} onGrade={async ()=>clozeResult('INCORRECT')} />)
  fireEvent.click(screen.getByRole('radio',{name:'C. Paging'}));fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));fireEvent.change(screen.getByRole('textbox'),{target:{value:'wrong'}})
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}));await screen.findByText('× Needs review')
  fireEvent.click(screen.getByRole('button',{name:'Try again'}));assert.ok(screen.getByText('Question 2 of 3'))
  assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'');assert.equal(screen.queryByText('× Needs review'),null)
  fireEvent.click(screen.getByRole('button',{name:'← Previous'}));assert.ok(screen.getByText('Correct.'))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  assert.equal(screen.getAllByRole('combobox').length,3)
})

test('cloze grading failure preserves input and retry does not mark incorrect', async () => {
  let attempts=0;render(<Quiz questions={[blank]} onSource={()=>{}} onGrade={async ()=>{if(++attempts===1)throw new Error('Checking unavailable. Retry.');return clozeResult('CORRECT')}} />)
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'  queue  '}});fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  await screen.findByRole('alert');assert.equal(screen.queryByText('× Needs review'),null)
  assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'  queue  ')
  fireEvent.click(screen.getByRole('button',{name:'Retry checking'}));await screen.findByText('✓ Correct');assert.equal(attempts,2)
})

test('cloze API sends only answer and retains normal page source links', async () => {
  stored=[newQuiz(['fill_blank'],[blank])];await openQuiz()
  let body:unknown;const original=globalThis.fetch
  globalThis.fetch=async (url,init)=>{if(String(url).includes('/cloze/'))body=JSON.parse(String(init?.body));return original(url,init)}
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Queue'}});fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  await screen.findByText('✓ Correct');assert.deepEqual(body,{answer:'Queue'})
  assert.ok(calls.some(c=>c.url.endsWith('/artifacts/quiz-v2/cloze/blank1/grade')))
  fireEvent.click(screen.getByRole('button',{name:'View source'}));await screen.findByRole('complementary',{name:'Source excerpt'})
})

test('cloze malformed response remains a retryable failure', async () => {
  stored=[newQuiz(['fill_blank'],[blank])];await openQuiz()
  globalThis.fetch=async ()=>new Response(JSON.stringify({unexpected:true}))
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Queue'}});fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  await screen.findByText('Answer checking returned an incomplete result. Keep your answer and retry.')
  assert.equal(screen.queryByText('× Needs review'),null);assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'Queue')
})

test('cloze unmount aborts pending answer check and duplicate submission is blocked', async () => {
  let signal:AbortSignal|undefined;let calls=0
  const view=render(<Quiz questions={[blank]} onSource={()=>{}} onGrade={async (_,__,current)=>{signal=current;calls++;return new Promise(()=>{})}} />)
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Queue'}});fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  fireEvent.keyDown(screen.getByRole('textbox'),{key:'Enter'});assert.equal(calls,1)
  view.unmount();assert.ok(signal?.aborted)
})
const labels = {mcq:'Multiple Choice',fill_blank:'Fill in the Blanks',matching:'Match the Following'}

test('MCQ text identity and checked answer survive next previous without reshuffling', () => {
  const deck=[mcq,blank,{...mcq,id:'m3'},blank,{...mcq,id:'m5'}]
  render(<Quiz questions={deck} onSource={()=>{}} />)
  const order=()=>screen.getAllByRole('radio').map(x=>(x as HTMLInputElement).value)
  const initial=order();assert.deepEqual(initial,['Queue','Stack','Paging','Tree'])
  fireEvent.click(screen.getByRole('radio',{name:'C. Paging'}))
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}));assert.ok(screen.getByText('Correct.'))
  for(let i=0;i<4;i++)fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  for(let i=0;i<4;i++)fireEvent.click(screen.getByRole('button',{name:'← Previous'}))
  assert.deepEqual(order(),initial);assert.ok((screen.getByRole('radio',{name:'C. Paging'}) as HTMLInputElement).checked)
  assert.ok(screen.getByText('Correct.'))
})

test('MCQ reordered artifact follows correct text identity and new artifact resets state', () => {
  const view=render(<Quiz key="old" questions={[mcq]} onSource={()=>{}} />)
  fireEvent.click(screen.getByRole('radio',{name:'C. Paging'}));fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  const fresh={...mcq,id:'fresh',options:['Tree','Paging','Queue','Stack']}
  view.rerender(<Quiz key="fresh" questions={[fresh]} onSource={()=>{}} />)
  assert.equal(screen.queryByText('Correct.'),null)
  assert.ok(screen.getAllByRole('radio').every(x=>!(x as HTMLInputElement).checked))
  fireEvent.click(screen.getByRole('radio',{name:'B. Paging'}));fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  assert.ok(screen.getByText('Correct.'))
})

test('matching stable IDs preserve shuffled order selections and score through navigation', () => {
  render(<Quiz questions={[matching,mcq]} onSource={()=>{}} />)
  const order=()=>Array.from((screen.getByRole('combobox',{name:'Match for Stack'}) as HTMLSelectElement).options).map(x=>x.value)
  const initial=order();assert.deepEqual(initial,['','R2','R3','R1'])
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Stack'}),{target:{value:'R2'}})
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Tree'}),{target:{value:'R2'}})
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Graph'}),{target:{value:'R3'}})
  assert.equal(screen.queryByText(/expected match/),null)
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}));assert.ok(screen.getByText('2 / 3 pairs correct.'))
  assert.ok(screen.getByText('Your match: Connects parent and child nodes.'))
  assert.ok(screen.getByText('Stack → Removes the most recent value first. (expected match)'))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));fireEvent.click(screen.getByRole('button',{name:'← Previous'}))
  assert.deepEqual(order(),initial);assert.equal((screen.getByRole('combobox',{name:'Match for Stack'}) as HTMLSelectElement).value,'R2')
  assert.ok(screen.getByText('2 / 3 pairs correct.'))
})

test('matching family prompt pair allocation and source links are explicit', async () => {
  const q={...matching,question:'Match each concept to its definition.'}
  stored=[{...newQuiz(['matching'],[q]),content:{questions:[q],requestedCount:12,learningItemCount:3,generatedCounts:{matching:1},matchingAllocation:{sets:1,pairs:3,requestedPairs:12}}}]
  await openQuiz();assert.ok(screen.getByText('Generated 3 of 12 requested learning items. 1 matching set · 3 pairs'))
  assert.ok(screen.getByText('1. Match each concept to its definition.'))
  for(const [label,value] of [['Stack','R1'],['Tree','R2'],['Graph','R3']])fireEvent.change(screen.getByRole('combobox',{name:`Match for ${label}`}),{target:{value}})
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}));assert.ok(screen.getByText('Correct.'))
  assert.ok(screen.getByText('3 / 3 pairs correct.'))
  fireEvent.click(screen.getAllByRole('button',{name:'View source'})[0]);await screen.findByRole('complementary',{name:'Source excerpt'})
})

test('quiz pager preserves answers and feedback while moving between questions', async () => {
  stored=[newQuiz(['mcq','fill_blank','matching'])];await openQuiz()
  fireEvent.click(screen.getByRole('radio',{name:'C. Paging'}));fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));assert.ok(screen.getByText('Question 2 of 3'))
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'Queue'}})
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));assert.equal(screen.getAllByRole('combobox').length,3)
  fireEvent.click(screen.getByRole('button',{name:'← Previous'}));assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'Queue')
  fireEvent.click(screen.getByRole('button',{name:'← Previous'}));assert.ok(screen.getByText('Correct.'))
})

test('quiz navigation clamps and try again resets current question', async () => {
  stored=[newQuiz(['mcq','fill_blank'])];await openQuiz()
  assert.ok((screen.getByRole('button',{name:'← Previous'}) as HTMLButtonElement).disabled)
  fireEvent.click(screen.getByRole('button',{name:'Next →'}));fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  assert.ok((screen.getByRole('button',{name:'Next →'}) as HTMLButtonElement).disabled)
  fireEvent.click(screen.getByRole('button',{name:'Try again'}));assert.ok(screen.getByText('Question 1 of 3'))
})

test('partial quiz preserves usable formats and displays exact shortfall counts', async () => {
  stored=[{...newQuiz(['mcq','matching'],[mcq]),content:{questions:[mcq],requestedCount:12,generatedCounts:{mcq:1,matching:0},messages:['Not enough matching relations.']}}];await openQuiz()
  assert.ok(screen.getByText('Generated 1 of 12 requested questions. Multiple Choice: 1 · Match the Following: 0'))
  assert.ok(screen.getByText('Not enough matching relations.'));assert.equal(screen.getAllByRole('radio').length,4)
})

test('quiz selector uses three checkboxes, defaults, and requires one selection', async () => {
  await openQuiz()
  const boxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
  assert.equal(boxes.length,3)
  assert.deepEqual(boxes.map(box => box.checked),[true,true,false])
  fireEvent.click(boxes[0]); fireEvent.click(boxes[1])
  assert.ok(screen.getByRole('alert').textContent?.includes('Select at least one question type.'))
  assert.ok((screen.getByRole('button',{name:'Generate Quiz'}) as HTMLButtonElement).disabled)
  fireEvent.click(screen.getByRole('button',{name:'Generate Quiz'}))
  assert.equal(calls.filter(call => call.method==='POST').length,0)
  fireEvent.click(boxes[2])
  assert.equal((screen.getByRole('button',{name:'Generate Quiz'}) as HTMLButtonElement).disabled,false)
})

const selections: QuizQuestionType[][] = [['mcq'],['fill_blank'],['matching'],['mcq','fill_blank'],['mcq','matching'],['fill_blank','matching'],['mcq','fill_blank','matching']]
for (const selection of selections) test(`quiz API passes the exact checkbox selection ${selection.join('+')}`, async () => {
  await openQuiz()
  for (const type of ['mcq','fill_blank','matching'] as QuizQuestionType[]) {
    const box=screen.getByRole('checkbox',{name:labels[type]}) as HTMLInputElement
    if (box.checked!==selection.includes(type)) fireEvent.click(box)
  }
  let requests=0
  globalThis.fetch = async (url, init={}) => {
    assert.ok(String(url).endsWith('/artifacts/quiz')); assert.equal(init.method,'POST')
    const body=JSON.parse(String(init.body))
    assert.deepEqual(body.questionTypes.slice().sort(),selection.slice().sort())
    assert.equal(body.questionCount,12); assert.equal(body.scope,'document')
    requests++
    return new Response(JSON.stringify({artifact:newQuiz(selection,[mcq,blank,matching].filter(q => selection.includes(q.type as QuizQuestionType))),cached:false}))
  }
  fireEvent.click(screen.getByRole('button',{name:'Generate Quiz'}))
  await screen.findByText('Artifact generated and saved for this session.')
  assert.equal(requests,1)
  assert.equal(screen.getAllByRole('button',{name:'Check answer'}).length,1)
  assert.ok(screen.getByText(`Question 1 of ${selection.length}`))
})

test('MCQ uses the independent answer, not options[0], and supports source feedback', async () => {
  stored=[newQuiz(['mcq'],[mcq])]; await openQuiz()
  assert.equal(screen.queryByText(mcq.sourceExcerpt),null)
  fireEvent.click(screen.getByRole('radio',{name:'A. Queue'}))
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  assert.ok(screen.getByText('Correct answer: Paging'))
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  fireEvent.click(screen.getByRole('radio',{name:'C. Paging'}))
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  assert.ok(screen.getByText('Correct.'))
  fireEvent.click(screen.getByRole('button',{name:'View source'}))
  await screen.findByRole('complementary',{name:'Source excerpt'})
})

test('matching uses shuffled IDs, requires all pairs, and provides partial feedback', async () => {
  stored=[newQuiz(['matching'],[matching])]; await openQuiz()
  const check=screen.getByRole('button',{name:'Check answer'}) as HTMLButtonElement
  assert.ok(check.disabled)
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Stack'}),{target:{value:'R1'}})
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Tree'}),{target:{value:'R2'}})
  assert.ok(check.disabled)
  fireEvent.change(screen.getByRole('combobox',{name:'Match for Graph'}),{target:{value:'R1'}})
  fireEvent.click(check)
  assert.ok(screen.getByText('2 / 3 pairs correct.'))
  assert.ok(screen.getByText(/Graph → Represents vertices and edges.*expected match/))
  assert.ok(screen.getByText('Graph represents vertices and edges.'))
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  for (const [text,id] of [['Stack','R1'],['Tree','R2'],['Graph','R3']]) fireEvent.change(screen.getByRole('combobox',{name:`Match for ${text}`}),{target:{value:id}})
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  assert.ok(screen.getByText('Correct.'))
})

test('mixed saved quizzes render all formats independently and reload without generation', async () => {
  stored=[newQuiz(['mcq','fill_blank','matching'])]; await openQuiz()
  assert.equal(screen.getAllByRole('radio').length,4)
  assert.equal(screen.queryByRole('textbox'),null)
  fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  assert.equal(screen.getAllByRole('textbox').length,1)
  fireEvent.change(screen.getByRole('textbox'),{target:{value:'  QUEUE!! '}})
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  await screen.findByText('✓ Correct')
  fireEvent.click(screen.getByRole('button',{name:'← Previous'}))
  assert.equal((screen.getByRole('radio',{name:'C. Paging'}) as HTMLInputElement).disabled,false)
  fireEvent.click(screen.getByRole('button',{name:'Try again'}))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  assert.equal((screen.getByRole('textbox') as HTMLInputElement).value,'')
  cleanup(); await openQuiz()
  assert.equal(screen.getAllByRole('checkbox').every(box => (box as HTMLInputElement).checked),true)
  assert.equal(calls.filter(call => call.method==='POST' && !call.url.includes('/cloze/')).length,0)
})

test('changing formats hides an incompatible cached quiz', async () => {
  stored=[newQuiz(['fill_blank'],[blank])]; await openQuiz()
  assert.ok(screen.getByRole('textbox'))
  fireEvent.click(screen.getByRole('checkbox',{name:'Multiple Choice'}))
  assert.equal(screen.queryByRole('textbox'),null)
  assert.ok(screen.getByText('No saved quiz for these question types yet.'))
  fireEvent.click(screen.getByRole('checkbox',{name:'Multiple Choice'}))
  assert.ok(screen.getByRole('textbox'))
})

test('legacy true-false and fill artifacts open explicitly without satisfying a new request', async () => {
  stored=[{id:'legacy',documentId:'doc1',type:'QUIZ',options:{},content:{questions:[
    {...blank,id:'oldblank'}, {id:'oldtrue',type:'true_false',question:'Paging divides memory.',correctAnswer:'True',sourceExcerpt:'Paging divides memory.',...provenance},
  ]}}]; await openQuiz()
  assert.equal(screen.queryByRole('textbox'),null)
  fireEvent.click(screen.getByRole('button',{name:'View previously saved quiz'}))
  assert.ok(screen.getByText(/This saved quiz uses the earlier format/))
  assert.ok(screen.getByRole('textbox'))
  fireEvent.click(screen.getByRole('button',{name:'Next →'}))
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'True'}})
  fireEvent.click(screen.getByRole('button',{name:'Check answer'}))
  assert.ok(screen.getByText('Correct.'))
})

test('quiz generation keeps controls disabled and prevents duplicate requests', async () => {
  await openQuiz()
  let finish: (value:Response)=>void=()=>{}; let requests=0
  globalThis.fetch=async ()=>{requests++;return new Promise(resolve=>{finish=resolve})}
  fireEvent.click(screen.getByRole('button',{name:'Generate Quiz'}))
  const button=screen.getByRole('button',{name:'Generating…'}) as HTMLButtonElement
  assert.ok(button.disabled)
  assert.ok((screen.getByRole('group',{name:'Question Types'}) as HTMLFieldSetElement).disabled)
  fireEvent.click(button); assert.equal(requests,1)
  await act(async ()=>finish(new Response(JSON.stringify({artifact:newQuiz(['mcq','fill_blank'],[mcq,blank]),cached:true}))))
  await screen.findByText('Loaded saved artifact.')
})

test('limited generation messages and empty quizzes remain useful without fabricated questions', async () => {
  stored=[{...newQuiz(['mcq'],[]),content:{questions:[],generatedCounts:{mcq:0},messages:['Not enough reliable source material was available for Multiple Choice.']}}]
  await openQuiz()
  assert.ok(screen.getByText('Not enough reliable source material was available for Multiple Choice.'))
  assert.ok(screen.getByText('Not enough reliable source content was found for this artifact.'))
  assert.equal(screen.queryByRole('button',{name:'Check answer'}),null)
  assert.ok(screen.getByRole('button',{name:'Generate Quiz'}))
})

test('quick and detailed summaries remain separate cached options', async () => {
  stored = ['quick', 'detailed'].map(mode => ({ id: mode, documentId: 'doc1', type: 'EXTRACTIVE_SUMMARY', options: { mode }, content: { sentences: [{ text: `${mode} source sentence.`, ...provenance }] } }))
  mount(); await screen.findByRole('button', { name: 'Generate' })
  fireEvent.click(screen.getByRole('tab', { name: 'Summary' }))
  assert.ok(screen.getByText('quick source sentence.'))
  fireEvent.change(screen.getByLabelText('Summary length'), { target: { value: 'detailed' } })
  assert.ok(screen.getByText('detailed source sentence.'))
})

for (const code of [401, 403, 404, 409, 500]) test(`safe error state for HTTP ${code}`, async () => {
  status = code; mount()
  const alert = await screen.findByRole('alert')
  assert.ok(!alert.textContent?.includes('sensitive backend diagnostic'))
  assert.ok(screen.getByRole('button', { name: 'Retry loading' }))
})

test('empty flashcards do not fabricate content', async () => {
  stored = [{ ...cards, content: { cards: [] } }]; mount()
  assert.ok(await screen.findByText(/Not enough definition-style content/))
  assert.equal(screen.queryByRole('button', { name: 'Reveal answer' }), null)
})

test('late response after switching documents cannot display old private content', async () => {
  let finish: (value: Response) => void = () => {}
  globalThis.fetch = async url => String(url).includes('doc1') ? new Promise(resolve => { finish = resolve }) : new Response(JSON.stringify({ artifacts: [] }))
  const view = mount()
  view.rerender(<KnowledgeTools documentId="doc2" title="Other.pdf" />)
  await screen.findByRole('button', { name: 'Generate' })
  await act(async () => finish(new Response(JSON.stringify({ artifacts: [cards] }))))
  assert.equal(screen.queryByRole('button', { name: 'Reveal answer' }), null)
})

test('API discards responses if token changed while awaiting source', async () => {
  let finish: (value: Response) => void = () => {}
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  const pending = getSource('doc1', 'c1')
  localStorage.setItem('luminar_token', 'session2')
  finish(new Response('{}'))
  await assert.rejects(pending, /account changed/)
})

test('generation busy state prevents duplicate submissions', async () => {
  mount(); await screen.findByRole('button', { name: 'Generate' })
  let finish: (value: Response) => void = () => {}
  globalThis.fetch = async () => new Promise(resolve => { finish = resolve })
  fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
  assert.ok((screen.getByRole('button', { name: 'Generating…' }) as HTMLButtonElement).disabled)
  await act(async () => finish(new Response(JSON.stringify({ artifact: cards, cached: false }))))
  await waitFor(() => assert.ok(screen.getByRole('button', { name: 'Reveal answer' })))
})

test('Know More opens Knowledge Tools for uploaded documents and preserves Ask Document', async () => {
  const { MemoryRouter } = await import('react-router-dom')
  const { LLMPage } = await import('../src/pages/LLMPage.tsx')
  dom.window.HTMLElement.prototype.scrollIntoView = () => {}
  const requests: string[] = []
  globalThis.fetch = async (url, init = {}) => {
    const path = String(url); requests.push(path)
    if (path.endsWith('/local-cache/scope')) return new Response(JSON.stringify({ enabled: false }))
    if (path.endsWith('/know-more/books')) return new Response(JSON.stringify({ books: [] }))
    if (path.endsWith('/rag/documents')) return new Response(JSON.stringify({ documents: [{ document_id: 'doc1', filename: 'Manual.pdf', pages: 4, chunks: 2 }] }))
    if (path.endsWith('/artifacts')) return new Response(JSON.stringify({ artifacts: [cards] }))
    if (path.endsWith('/rag/ask')) {
      assert.equal(JSON.parse(String(init.body)).document_id, 'doc1')
      return new Response(JSON.stringify({ answer: 'Independent document answer.', sources: [] }))
    }
    throw new Error(`Unexpected request: ${path}`)
  }
  render(<MemoryRouter><LLMPage /></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: /Manual.pdf.*Active/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Knowledge Tools' }))
  await screen.findByRole('button', { name: 'Reveal answer' })
  assert.ok(!requests.some(path => path.endsWith('/rag/ask')))
  fireEvent.click(screen.getByRole('button', { name: 'Ask Document' }))
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: 'Explain paging' } })
  fireEvent.keyDown(input, { key: 'Enter' })
  // The answer renderer is lazy-loaded; a cold module import can exceed the
  // default one-second DOM query deadline on this Windows development host.
  assert.ok(await screen.findByText('Independent document answer.', {}, { timeout: 10000 }))
  fireEvent.click(screen.getByRole('button', { name: 'Knowledge Tools' }))
  await screen.findByRole('button', { name: 'Reveal answer' })
})
