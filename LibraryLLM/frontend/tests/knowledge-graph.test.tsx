import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { KnowledgeGraphPage } = await import('../src/pages/KnowledgeGraphPage.tsx')
const meta = { books: 5_000_000, edges: 29_000_000, features: { author: 100, subject: 500 }, isolated_books: 1, missing_authors: 2, missing_subjects: 3, created_at: '2026-10-02T00:00:00Z', catalogue_hash: 'fixture' }
const seed = { work_id: 'OL1W', title: 'Starting Book', authors: ['An Author'], subjects: ['Science'] }
const other = { work_id: 'OL2W', title: 'Another Book', authors: ['Other Author'], subjects: ['Science'] }
const data = { seed, recommendations: [{ ...other, score: .8, reason_paths: [{ nodes: ['OL1W', 'subject:science', 'OL2W'], kind: 'subject', label: 'Science', contribution: .8, catalogue_degree: 4, provenance: [] }] }], candidate_count: 4, reason: 'metadata', snapshot: meta,
  exploration: { nodes: [{ id: 'OL1W', label: seed.title, kind: 'book', seed: true }, { id: 'OL2W', label: other.title, kind: 'book', seed: false }, { id: 'subject:science', label: 'Science', kind: 'subject', seed: false }], edges: [{ source: 'OL1W', target: 'subject:science', predicate: 'HAS_SUBJECT' }, { source: 'OL2W', target: 'subject:science', predicate: 'HAS_SUBJECT' }], reason_paths_per_book_shown: 3 } }
let original: typeof fetch
let calls: string[] = []
let compareFails = false
beforeEach(() => {
  localStorage.setItem('luminar_token', 'fixture-token'); original = globalThis.fetch; calls = []; compareFails = false
  globalThis.fetch = async url => {
    calls.push(String(url))
    if (String(url).endsWith('/compare') && compareFails) return new Response(JSON.stringify({ detail: 'Existing recommender unavailable' }), { status: 503 })
    const body = String(url).endsWith('/meta') ? meta : String(url).includes('/books?') ? { books: [seed, other] } : String(url).endsWith('/compare')
      ? { ...data, existing: [other], metrics: { overlap_at_k: 1, intersection_count: 1, kg_only_ids: [], existing_diversity: { subject_pairwise_distance: null }, kg_diversity: { subject_pairwise_distance: null } } } : data
    return new Response(JSON.stringify(body), { status: 200 })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
async function mount() { render(<MemoryRouter><KnowledgeGraphPage /></MemoryRouter>); await waitFor(() => assert.equal(screen.getByLabelText('Starting book').getAttribute('disabled'), null)) }
async function explore() { fireEvent.click(screen.getByRole('button', { name: 'Explore connections' })); await screen.findByRole('region', { name: 'Interactive catalogue graph' }) }

test('graph lookup and recommendation remain opt-in and show reason paths', async () => {
  await mount(); assert.equal(calls.some(url => url.endsWith('/more-like-this')), false)
  await explore(); assert.ok(screen.getByRole('button', { name: 'Shared subject: Science' }))
  assert.ok(screen.getByText('Similarity 0.800'))
  assert.equal(calls.some(url => url.endsWith('/compare')), false)
})
test('keyboard node selection, subject filter and reseeding clear stale comparisons', async () => {
  await mount(); await explore()
  fireEvent.keyDown(screen.getByRole('button', { name: 'Inspect subject: Science' }), { key: 'Enter' })
  assert.ok(screen.getByRole('heading', { name: 'Science' }))
  fireEvent.click(screen.getByLabelText('Subjects'))
  assert.equal(screen.queryByRole('button', { name: 'Inspect subject: Science' }), null)
  fireEvent.click(screen.getByRole('button', { name: 'Inspect book: Another Book' }))
  fireEvent.click(screen.getByRole('button', { name: 'Use as starting book' }))
  assert.equal(screen.queryByRole('region', { name: 'Interactive catalogue graph' }), null)
  assert.equal((screen.getByLabelText('Starting book') as HTMLSelectElement).value, 'OL2W')
})
test('compare explicitly requests the existing recommender and renders both lists', async () => {
  await mount(); await explore(); fireEvent.click(screen.getByRole('button', { name: 'Compare with existing recommender' }))
  await screen.findByRole('region', { name: 'Recommendation comparison metrics' })
  assert.ok(calls.some(url => url.endsWith('/compare')))
  assert.ok(screen.getByRole('heading', { name: 'Existing recommender' }))
  assert.ok(screen.getByText('100%'))
})
test('unavailable existing recommender does not fabricate comparison metrics', async () => {
  await mount(); await explore(); compareFails = true
  fireEvent.click(screen.getByRole('button', { name: 'Compare with existing recommender' }))
  await screen.findByRole('alert'); assert.equal(screen.queryByRole('region', { name: 'Recommendation comparison metrics' }), null)
  assert.ok(screen.getByRole('region', { name: 'Interactive catalogue graph' }))
})
test('aborted request cannot replace a newly selected seed', async () => {
  await mount(); let release: ((value: Response) => void) | undefined
  globalThis.fetch = async () => new Promise<Response>(resolve => { release = resolve })
  fireEvent.click(screen.getByRole('button', { name: 'Explore connections' }))
  fireEvent.change(screen.getByLabelText('Starting book'), { target: { value: 'OL2W' } })
  release?.(new Response(JSON.stringify(data), { status: 200 }))
  await waitFor(() => assert.equal(screen.queryByRole('region', { name: 'Interactive catalogue graph' }), null))
})
