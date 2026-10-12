import assert from 'node:assert/strict'
import { test, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import { readFileSync } from 'node:fs'
import { comparison, wideTable, longMath, wideCode } from './fixtures/rag-formatting'
import { normalizeRAGMarkdown } from '../src/lib/ragAnswerMarkdown'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage,
  sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, cleanup, fireEvent } = await import('@testing-library/react')
const { RAGAnswer } = await import('../src/components/rag/RAGAnswer')
afterEach(cleanup)
const mount = (text: string) => render(<RAGAnswer text={text} />).container
const css = readFileSync(new URL('../src/components/rag/RAGAnswer.css', import.meta.url), 'utf8')

test('test_rag_markdown_heading', () => {
  mount('# Title\n\n## Section\n\n### Detail\n\n#### Subsection')
  assert.equal(screen.getByRole('heading', { name: 'Title' }).tagName, 'H2')
  assert.equal(screen.getAllByRole('heading').length, 4)
  assert.equal(document.querySelector('h1'), null)
})
test('test_rag_markdown_bold', () => assert.equal(mount('**important** and __preserved__').querySelectorAll('strong').length, 2))
test('test_rag_markdown_italic', () => assert.equal(mount('*emphasis*').querySelector('em')?.textContent, 'emphasis'))
test('test_rag_markdown_bullets', () => {
  const root = mount('- First\n- Second\n  - Nested'); assert.equal(root.querySelectorAll('ul').length, 2); assert.equal(root.querySelectorAll('li').length, 3)
})
test('test_rag_markdown_numbered_list', () => assert.equal(mount('1. First\n2. Second').querySelectorAll('ol > li').length, 2))
test('test_rag_inline_code', () => assert.equal(mount('`10101011`').querySelector('code')?.textContent, '10101011'))
test('test_rag_code_block', () => {
  const original = String.raw`\(10101011 \times T\)`
  const root = mount('```math\n' + original + '\n```'); assert.equal(root.querySelector('pre code')?.textContent, original + '\n'); assert.equal(root.querySelector('pre')?.tabIndex, 0)
})
test('test_rag_inline_math', () => {
  const expression = String.raw`2 \times T_{\text{fr}}`
  const root = mount('Time: \\(' + expression + '\\) seconds.'); assert.equal(root.querySelector('annotation')?.textContent, expression); assert.ok(root.querySelector('math')); assert.ok(root.querySelector('.katex-html'))
})
test('test_rag_display_math', () => {
  const root = mount(String.raw`\[T_{\frac{\text{slot}}{2}} = \frac{2T}{3}\]` + '\n\n$$\n10101011 = 10101011\n$$')
  assert.equal(root.querySelectorAll('.katex-display').length, 2); assert.equal(root.querySelector('pre'), null); assert.equal(root.querySelector('annotation')?.textContent, String.raw`T_{\frac{\text{slot}}{2}} = \frac{2T}{3}`)
})
test('test_rag_table', () => { const root = mount(comparison); assert.equal(root.querySelectorAll('th').length, 3); assert.equal(root.querySelectorAll('td').length, 6) })
test('test_rag_table_mobile_scroll', () => { mount(wideTable); assert.equal(screen.getByRole('region', { name: 'Answer table' }).tabIndex, 0); assert.match(css, /\.rag-answer-scroll[^}]*overflow-x: auto/); assert.equal(document.querySelectorAll('th').length, 12) })
test('test_rag_math_mobile_overflow', () => { mount(longMath); assert.equal(screen.getByRole('region', { name: 'Answer equation' }).tabIndex, 0); assert.match(css, /\.rag-answer \.katex-display \{[^}]*overflow-x: auto/); assert.equal(document.querySelector('annotation')?.textContent?.split(' + ').length, 45) })
test('test_rag_code_mobile_overflow', () => { mount(wideCode); assert.match(css, /\.rag-answer pre \{[^}]*overflow-x: auto/); assert.equal(document.querySelector('pre code')?.textContent?.trim(), '10101011'.repeat(100)) })
test('test_rag_malformed_math_fallback', () => {
  const root = mount(String.raw`Before $\frac{2}{$ after and $\unknowncommand{10101011}$`)
  assert.equal(root.querySelectorAll('.rag-math-fallback').length, 2)
  assert.equal(root.querySelector('.rag-math-fallback')?.textContent, String.raw`\frac{2}{`)
  assert.ok(root.textContent?.includes('after')); assert.ok(root.textContent?.includes('10101011'))
})
test('incomplete delimiters and unclosed bold never crash', () => { const root = mount(String.raw`**Unclosed bold and \(2 \times T`); assert.ok(root.textContent?.includes('Unclosed bold')); assert.equal(root.querySelector('code')?.textContent, String.raw`\(2 \times T`) })
test('light normalization preserves code, escaped delimiters and CRLF', () => {
  const original = String.raw`Code <tick>\(2\)<tick> and \\(literal\\) and \(T_{\frac{\text{slot}}{2}}\)`.replaceAll('<tick>', '`')
  const normalized = normalizeRAGMarkdown(original); assert.ok(normalized.includes(String.raw`\(2\)`)); assert.ok(normalized.includes(String.raw`\\(literal\\)`)); assert.ok(normalized.includes(String.raw`$T_{\frac{\text{slot}}{2}}$`)); assert.equal(normalizeRAGMarkdown('a\r\nb'), 'a\nb')
})
test('technical literals and math source survive JSON transport exactly', () => {
  const input = JSON.parse(JSON.stringify({ answer: comparison })).answer
  const root = mount(input); assert.ok(root.textContent?.includes('10101011')); assert.ok(root.textContent?.includes('36.8%')); assert.ok(root.textContent?.includes('0.184'))
  assert.deepEqual([...root.querySelectorAll('annotation')].map(n => n.textContent), [String.raw`2 \times T_{\text{fr}}`, String.raw`T_{\text{fr}}`, String.raw`2 \times T_{\text{fr}}`, String.raw`T_{\text{fr}}`, String.raw`T_{\frac{\text{slot}}{2}} = \frac{2T}{3}`])
  assert.equal(root.querySelector('h3')?.textContent, 'Differences Between Pure ALOHA and Slotted ALOHA'); assert.equal(root.querySelector('blockquote')?.textContent?.trim(), 'Compare against the source.')
})
test('test_rag_raw_html_escaped', () => { const root = mount('<b>Raw HTML</b>'); assert.equal(root.querySelector('b'), null); assert.ok(root.textContent?.includes('<b>')) })
test('test_rag_xss_script_blocked', () => { const root = mount('<script>window.compromised = true</script>\n\n<img src=x onerror="window.compromised=true">'); assert.equal(root.querySelector('script, img, [onerror]'), null); assert.equal((dom.window as any).compromised, undefined) })
test('test_rag_javascript_url_blocked', () => { const root = mount('[click](javascript:alert%281%29) [external](https://example.com) ![private image](https://example.com/tracker)'); assert.equal(root.querySelector('a, img'), null); assert.ok(root.textContent?.includes('click')); assert.ok(root.textContent?.includes('external')) })
test('untrusted math cannot create links, images or arbitrary HTML attributes', () => {
  const root = mount(String.raw`$\href{javascript:alert(1)}{click}$ $\includegraphics{https://example.com/tracker}$ $\htmlClass{evil}{x}$`)
  assert.equal(root.querySelector('a, img, .evil, [onerror]'), null)
})
test('macro expansion is bounded and macros do not persist between expressions', () => {
  const root = mount(String.raw`$\def\loop{\loop}\loop$ and $\newcommand{\secret}{10101011}\secret$ and $\secret$`)
  assert.ok(root.querySelectorAll('.rag-math-fallback').length >= 2)
})
test('very long words and large tables retain all content', () => { const root = mount('A'.repeat(20000) + '\n\n' + wideTable); assert.ok(root.textContent?.includes('A'.repeat(20000))); assert.match(css, /overflow-wrap: anywhere/); assert.equal(root.querySelectorAll('th').length, 12) })
test('formatting makes zero additional network calls', () => {
  const original = globalThis.fetch; let calls = 0
  globalThis.fetch = async () => { calls++; throw Error('Unexpected rendering request') }
  try { mount(comparison); assert.equal(calls, 0) } finally { globalThis.fetch = original }
})

for (const verdict of ['SUPPORTED', 'NOT_SUPPORTED']) test(verdict === 'SUPPORTED' ? 'test_rag_source_cards_unchanged' : 'test_rag_grounded_badge_unchanged', async () => {
  const { MemoryRouter } = await import('react-router-dom')
  const { LLMPage } = await import('../src/pages/LLMPage')
  const { useAuthStore } = await import('../src/store/useAuthStore')
  const { act } = await import('@testing-library/react')
  dom.window.HTMLElement.prototype.scrollIntoView = () => {}
  localStorage.setItem('luminar_token', 'formatting-session')
  act(() => useAuthStore.setState({ token: 'formatting-session', isAuthenticated: true }))
  const original = globalThis.fetch; const calls: string[] = []
  globalThis.fetch = async url => {
    const path = String(url); calls.push(path)
    if (path.endsWith('/local-cache/scope')) return Response.json({ enabled: false })
    if (path.endsWith('/know-more/books')) return Response.json({ books: [] })
    if (path.endsWith('/rag/documents')) return Response.json({ documents: [{ document_id: 'doc1', filename: 'Manual.pdf', pages: 4, chunks: 2 }] })
    if (path.endsWith('/rag/ask')) return Response.json({ answer: comparison + '\n\n[False citation](https://example.com)', verdict, sources: [{ filename: 'Manual.pdf', page: 4, chunk_id: 'trusted-source' }] })
    throw Error('Unexpected ' + path)
  }
  try {
    render(<MemoryRouter><LLMPage /></MemoryRouter>)
    fireEvent.click(await screen.findByRole('button', { name: /Manual.pdf.*Active/ }))
    const input = screen.getByRole('textbox'); fireEvent.change(input, { target: { value: 'Compare ALOHA' } }); fireEvent.keyDown(input, { key: 'Enter' })
    await screen.findByRole('heading', { name: 'Differences Between Pure ALOHA and Slotted ALOHA' })
    assert.ok(screen.getByText('Sources')); assert.ok(screen.getByText('p.4'))
    assert.ok(screen.getByText(verdict === 'NOT_SUPPORTED' ? 'Unsupported' : 'Grounded'))
    const cards = document.querySelector('.rag-chat-sources')
    assert.ok(cards?.textContent?.includes('Manual.pdf')); assert.ok(!cards?.textContent?.includes('False citation'))
    assert.equal(document.querySelector('.rag-answer a'), null)
    assert.equal(calls.filter(p => p.endsWith('/rag/ask')).length, 1)
  } finally { cleanup(); globalThis.fetch = original }
})
