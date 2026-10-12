import assert from 'node:assert/strict'
import { test, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import { layoutKnowledgeMap, mapCardWidth, mapCardHeight } from '../src/components/knowledge/mapLayout'
import type { MapNode } from '../src/lib/knowledgeArtifacts'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor } = await import('@testing-library/react')
const { KnowledgeMap } = await import('../src/components/knowledge/KnowledgeMap')
afterEach(cleanup)
const nodes: MapNode[] = [{ id: 'root', type: 'document', label: 'Document', sourceChunkIds: [] }]
const edges: {source: string; target: string; relation: string}[] = []
for (let i = 0; i < 16; i++) {
  nodes.push({ id: 'c' + i, type: 'concept', label: 'Concept ' + i, sourceChunkIds: ['source' + i] }, { id: 'd' + i, type: 'detail', label: 'Detail ' + i, sourceChunkIds: ['source' + i] })
  edges.push({ source: 'root', target: 'c' + i, relation: 'contains' }, { source: 'c' + i, target: 'd' + i, relation: 'explains' })
}
const mount = () => render(<KnowledgeMap nodes={nodes} edges={edges} onSource={() => {}} />)

test('balanced branches occupy both sides, center their parent, and never overlap', () => {
  const layout = layoutKnowledgeMap(nodes, edges)
  const root = layout.positions.get('root')!
  const branches = nodes.filter(n => n.type === 'concept').map(n => layout.positions.get(n.id)!)
  assert.ok(branches.some(p => p.x < root.x) && branches.some(p => p.x > root.x))
  assert.equal(root.y + mapCardHeight / 2, layout.height / 2)
  const positions = [...layout.positions.values()]
  for (let i = 0; i < positions.length; i++) for (let j = i + 1; j < positions.length; j++) {
    const a = positions[i], b = positions[j]
    assert.ok(Math.abs(a.x - b.x) >= mapCardWidth || Math.abs(a.y - b.y) >= mapCardHeight)
  }
})
test('zoomed-out layout spreads connections across available canvas without mutating source data', () => {
  const before = JSON.stringify({nodes, edges}), normal = layoutKnowledgeMap(nodes, edges)
  const wide = layoutKnowledgeMap(nodes, edges, normal.width * 2, normal.height * 2)
  const gap = (layout: typeof normal) => Math.abs(layout.positions.get('c0')!.x - layout.positions.get('root')!.x)
  assert.ok(gap(wide) > gap(normal)); assert.equal(JSON.stringify({nodes, edges}), before)
})
test('cycles, duplicate parents, dangling edges and disconnected nodes keep every valid node', () => {
  const layout = layoutKnowledgeMap([...nodes, {id:'orphan',type:'concept',label:'Orphan',sourceChunkIds:[]}], [...edges, {source:'d0',target:'root'}, {source:'c1',target:'d0'}, {source:'missing',target:'c0'}])
  assert.equal(layout.positions.size, nodes.length + 1)
  assert.ok([...layout.positions.values()].every(p => Number.isFinite(p.x) && Number.isFinite(p.y)))
})
test('default fits the complete graph and zoom-out works below that default', () => {
  mount(); const svg = screen.getByRole('group', {name:'Document concept map'})
  const before = Number(svg.getAttribute('data-zoom')); assert.ok(before < 1)
  fireEvent.click(screen.getByRole('button', {name:'Zoom out'})); assert.ok(Number(svg.getAttribute('data-zoom')) < before)
  fireEvent.click(screen.getByRole('button', {name:'Reset view'})); assert.equal(Number(svg.getAttribute('data-zoom')), before)
})
test('wheel panning moves the canvas and prevents the surrounding page from scrolling', () => {
  mount(); const svg = screen.getByRole('group', {name:'Document concept map'})
  const group = svg.querySelector('g')!, before = group.getAttribute('transform')
  const wheel = new dom.window.WheelEvent('wheel', {deltaX:20,deltaY:40,bubbles:true,cancelable:true})
  fireEvent(svg,wheel)
  assert.ok(wheel.defaultPrevented); assert.notEqual(group.getAttribute('transform'), before)
  fireEvent.click(screen.getByRole('button',{name:'Reset view'}))
  assert.equal(group.getAttribute('transform'), before)
})
test('fullscreen fills a modal outside the app, traps focus, and Escape restores it', async () => {
  mount(); const opener = screen.getByRole('button', {name:'Fullscreen'}); opener.focus(); fireEvent.click(opener)
  const dialog = screen.getByRole('dialog', {name:'Fullscreen mind map'})
  assert.ok(dialog.parentElement === document.body); assert.equal(dialog.getAttribute('aria-modal'), 'true')
  assert.equal(document.body.style.overflow, 'hidden'); assert.equal((document.getElementById('root') as any).inert, true)
  const last = dialog.querySelectorAll('[tabindex="0"]'); (last[last.length - 1] as HTMLElement).focus()
  fireEvent.keyDown(window, {key:'Tab'}); assert.ok(document.activeElement === screen.getByRole('button', {name:'Zoom in'}), `Focus was on ${document.activeElement?.tagName} ${document.activeElement?.getAttribute('aria-label')}`)
  fireEvent.keyDown(window, {key:'Escape'}); assert.equal(screen.queryByRole('dialog'), null)
  await waitFor(() => assert.ok(document.activeElement === screen.getByRole('button', {name:'Fullscreen'})))
  assert.equal(document.body.style.overflow, '')
})
test('concept selection and trusted source controls stay usable in fullscreen', () => {
  const calls: string[] = []
  render(<KnowledgeMap nodes={nodes} edges={edges} onSource={id => calls.push(id)} sourcePanel={<aside aria-label="Source excerpt">Trusted document excerpt</aside>} />)
  fireEvent.click(screen.getByRole('button', {name:'Fullscreen'})); fireEvent.click(screen.getByRole('button', {name:'Concept 0'}))
  fireEvent.click(screen.getByRole('button', {name:'View source'})); assert.deepEqual(calls, ['source0'])
  assert.ok(screen.getByRole('dialog').contains(screen.getByRole('complementary', {name:'Source excerpt'})))
})
test('unmounting a fullscreen private map clears its content and restores page scrolling', () => {
  const view = mount(); fireEvent.click(screen.getByRole('button', {name:'Fullscreen'})); view.unmount()
  assert.equal(screen.queryByRole('dialog'), null); assert.equal(document.body.style.overflow, '')
  assert.equal(document.body.textContent?.includes('Concept 0'), false)
})
