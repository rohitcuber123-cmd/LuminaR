import type { MapNode } from '../../lib/knowledgeArtifacts'

export const mapCardWidth = 205, mapCardHeight = 68

/** Balanced tree positioning, without changing source nodes or cross-links. */
export function layoutKnowledgeMap(nodes: MapNode[], edges: { source: string; target: string }[], availableWidth = 0, availableHeight = 0) {
  const ids = new Set(nodes.map(n => n.id)), children = new Map(nodes.map(n => [n.id, [] as string[]]))
  const outgoing = new Map(nodes.map(n => [n.id, [] as string[]]))
  for (const edge of edges) if (ids.has(edge.source) && ids.has(edge.target) && edge.source !== edge.target) outgoing.get(edge.source)!.push(edge.target)
  const root = nodes.find(n => n.type === 'document')?.id || nodes[0]?.id
  if (!root) return { width: 400, height: 300, positions: new Map<string, { x: number; y: number }>() }
  const seen = new Set<string>(), depths = new Map<string, number>(), order: string[] = []
  function visit(start: string, initialDepth: number) {
    const queue = [start]; seen.add(start); depths.set(start, initialDepth)
    for (let i = 0; i < queue.length; i++) {
      const id = queue[i]; order.push(id)
      for (const target of outgoing.get(id) || []) if (!seen.has(target)) {
        seen.add(target); depths.set(target, depths.get(id)! + 1); children.get(id)!.push(target); queue.push(target)
      }
    }
  }
  visit(root, 0)
  // Give disconnected components space without drawing invented edges.
  for (const node of nodes) if (!seen.has(node.id)) { children.get(root)!.push(node.id); visit(node.id, 1) }
  const weight = new Map<string, number>()
  for (const id of order.slice().reverse()) weight.set(id, Math.max(1, children.get(id)!.reduce((sum, child) => sum + (weight.get(child) || 1), 0)))
  const sides: string[][] = [[], []], counts = [0, 0]
  for (const branch of children.get(root)!) {
    const side = counts[0] <= counts[1] ? 0 : 1
    sides[side].push(branch); counts[side] += weight.get(branch) || 1
  }
  const depth = Math.max(0, ...depths.values())
  const width = Math.max(mapCardWidth + depth * 2 * (mapCardWidth + 96) + 64, availableWidth)
  const height = Math.max(300, Math.max(1, ...counts) * (mapCardHeight + 24) + 64, availableHeight)
  const gap = depth ? (width - mapCardWidth - 64) / (2 * depth) : 0
  const centerX = (width - mapCardWidth) / 2
  const positions = new Map([[root, { x: centerX, y: (height - mapCardHeight) / 2 }]])
  for (let side = 0; side < 2; side++) {
    const tasks: { id: string; top: number; span: number }[] = []
    let top = 32
    for (const id of sides[side]) {
      const span = (height - 64) * (weight.get(id) || 1) / counts[side]
      tasks.push({ id, top, span }); top += span
    }
    for (let i = 0; i < tasks.length; i++) {
      const { id, top, span } = tasks[i]
      positions.set(id, { x: centerX + (side ? -1 : 1) * depths.get(id)! * gap, y: top + (span - mapCardHeight) / 2 })
      let childTop = top
      for (const child of children.get(id)!) {
        const childSpan = span * (weight.get(child) || 1) / (weight.get(id) || 1)
        tasks.push({ id: child, top: childTop, span: childSpan }); childTop += childSpan
      }
    }
  }
  return { width, height, positions }
}
