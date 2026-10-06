import { useRef, useState } from 'react'
import type { MapNode } from '../../lib/knowledgeArtifacts'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'

export function KnowledgeMap({ nodes, edges, onSource }: {
  nodes: MapNode[]; edges: { source: string; target: string; relation: string }[]; onSource: (id: string) => void
}) {
  const [zoom, setZoom] = useState(1), [pan, setPan] = useState({ x: 0, y: 0 }), [selected, setSelected] = useState<MapNode | null>(null)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const parents = new Map(edges.map(e => [e.target, e.source]))
  const depths = new Map<string, number>()
  function depth(id: string, visited = new Set<string>()): number {
    if (visited.has(id)) return 0
    visited.add(id)
    const parent = parents.get(id)
    return parent ? 1 + depth(parent, visited) : 0
  }
  nodes.forEach(n => depths.set(n.id, depth(n.id)))
  const rows = new Map<number, number>()
  const positions = new Map(nodes.map(node => {
    const d = depths.get(node.id) || 0, row = rows.get(d) || 0; rows.set(d, row + 1)
    return [node.id, { x: 30 + d * 250, y: 25 + row * 92 }]
  }))
  const width = Math.max(750, (Math.max(0, ...depths.values()) + 1) * 250 + 30)
  const height = Math.max(320, Math.max(1, ...rows.values()) * 92 + 30)
  return <div>
    <div className="mb-3 flex flex-wrap gap-2"><button className={toolButton} onClick={() => setZoom(z => Math.min(2, z + .2))}>Zoom in</button><button className={toolButton} onClick={() => setZoom(z => Math.max(.4, z - .2))}>Zoom out</button><button className={toolButton} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}>Reset view</button></div>
    <p className="mb-2 text-xs text-ink-soft">Drag to pan, scroll to explore, or select a concept to view its sources.</p>
    <div className="max-h-[520px] overflow-auto border border-line bg-panel">
      <svg role="group" aria-label="Document concept map" width={width * zoom} height={height * zoom} viewBox={`0 0 ${width} ${height}`} style={{ touchAction: 'none' }}
        onPointerDown={e => { if ((e.target as Element).closest('[role="button"]')) return; drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }; e.currentTarget.setPointerCapture(e.pointerId) }}
        onPointerMove={e => { if (drag.current) setPan({ x: drag.current.px + (e.clientX - drag.current.x) / zoom, y: drag.current.py + (e.clientY - drag.current.y) / zoom }) }}
        onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}>
        <g transform={`translate(${pan.x},${pan.y})`}>
          {edges.map(edge => { const from = positions.get(edge.source), to = positions.get(edge.target); return from && to ? <path key={`${edge.source}:${edge.target}`} d={`M${from.x + 205},${from.y + 32} C${from.x + 230},${from.y + 32} ${to.x - 25},${to.y + 32} ${to.x},${to.y + 32}`} fill="none" stroke="currentColor" opacity=".35" /> : null })}
          {nodes.map(node => { const p = positions.get(node.id)!; const words = node.label.match(/.{1,25}(?:\s|$)|.{1,25}/g) || [node.label]; return <g key={node.id} role="button" tabIndex={0} aria-label={node.label} onClick={() => setSelected(node)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(node) } }} className="cursor-pointer text-ink" transform={`translate(${p.x},${p.y})`}>
            <title>{node.label}</title><rect width="205" height="68" rx="4" className={selected?.id === node.id ? 'fill-brand/15 stroke-brand' : 'fill-paper stroke-ink-soft'} />
            <text x="10" y="25" fill="currentColor" fontSize="12">{words.slice(0, 2).map((word, i) => <tspan key={i} x="10" dy={i ? 18 : 0}>{word.trim()}{i === 1 && words.length > 2 ? '…' : ''}</tspan>)}</text>
          </g> })}
        </g>
      </svg>
    </div>
    {selected && <div className="mt-4 border border-line p-4"><h3 className="font-medium">{selected.label}</h3>{selected.sourceChunkIds.length > 0 && <SourceLink source={selected} onSource={onSource} />}</div>}
  </div>
}
