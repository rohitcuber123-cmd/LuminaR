import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Maximize2, Minimize2 } from 'lucide-react'
import type { MapNode } from '../../lib/knowledgeArtifacts'
import { SourceLink } from './SourceLink'
import { toolButton } from './styles'
import { layoutKnowledgeMap, mapCardHeight, mapCardWidth } from './mapLayout'

export function KnowledgeMap({ nodes, edges, onSource, sourcePanel }: {
  nodes: MapNode[]; edges: { source: string; target: string; relation: string }[]; onSource: (id: string) => void; sourcePanel?: ReactNode
}) {
  const [level, setLevel] = useState(1), [pan, setPan] = useState({ x: 0, y: 0 })
  const [selected, setSelected] = useState<MapNode | null>(null), [fullscreen, setFullscreen] = useState(false)
  const [size, setSize] = useState({ width: 960, height: 540 })
  const viewport = useRef<HTMLDivElement>(null), fullscreenButton = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLElement>(null)
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null)
  const natural = useMemo(() => layoutKnowledgeMap(nodes, edges), [nodes, edges])
  const fit = Math.min(1, Math.max(1, size.width - 48) / natural.width, Math.max(1, size.height - 48) / natural.height)
  const zoom = fit * level
  // At lower zoom the layout opens up between branches while cards shrink.
  const layout = useMemo(() => layoutKnowledgeMap(nodes, edges, (size.width - 48) / zoom, (size.height - 48) / zoom), [nodes, edges, size, zoom])
  const reset = () => { setLevel(1); setPan({ x: 0, y: 0 }) }
  const changeZoom = (factor: number) => setLevel(value => Math.max(.1, Math.min(2.5 / fit, value * factor)))

  useEffect(() => {
    const element = viewport.current
    if (!element) return
    const measure = () => {
      const { width, height } = element.getBoundingClientRect()
      if (width > 0 && height > 0) setSize(current => current.width === width && current.height === height ? current : { width, height })
    }
    measure()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    observer?.observe(element)
    const wheel = (event: WheelEvent) => {
      event.preventDefault()
      setPan(value => ({ x: value.x - event.deltaX, y: value.y - event.deltaY }))
    }
    element.addEventListener('wheel', wheel, { passive: false })
    window.addEventListener('resize', measure)
    return () => { observer?.disconnect(); element.removeEventListener('wheel', wheel); window.removeEventListener('resize', measure) }
  }, [fullscreen])

  useEffect(() => {
    if (!fullscreen) return
    const root = document.getElementById('root'), previousInert = root?.inert
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    if (root) root.inert = true
    fullscreenButton.current?.focus()
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setFullscreen(false); return }
      if (event.key !== 'Tab') return
      const controls = [...(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled),[tabindex="0"],a[href]') || [])]
      const first = controls[0], last = controls.at(-1)
      if (event.shiftKey && (document.activeElement === first || !dialog.current?.contains(document.activeElement))) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && (document.activeElement === last || !dialog.current?.contains(document.activeElement))) { event.preventDefault(); first?.focus() }
    }
    window.addEventListener('keydown', keyboard)
    const restoreFocus = () => fullscreenButton.current?.focus()
    return () => {
      window.removeEventListener('keydown', keyboard)
      document.body.style.overflow = previousOverflow
      if (root) root.inert = previousInert ?? false
      // The inline button is remounted when the portal closes.
      queueMicrotask(restoreFocus)
    }
  }, [fullscreen])

  const content = <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
    <div className="flex shrink-0 flex-wrap items-center gap-2">
      <button className={toolButton} disabled={zoom >= 2.5} onClick={() => changeZoom(1.25)}>Zoom in</button>
      <button className={toolButton} disabled={level <= .1} onClick={() => changeZoom(.8)}>Zoom out</button>
      <output aria-label="Zoom level" className="min-w-10 text-center text-xs tabular-nums text-ink-soft">{Math.round(zoom * 100)}%</output>
      <button className={toolButton} title="Fit the entire map to the canvas" onClick={reset}>Reset view</button>
      <button ref={fullscreenButton} className={toolButton + ' ml-auto inline-flex items-center gap-2'} onClick={() => setFullscreen(value => !value)}>
        {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}{fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
      </button>
    </div>
    <p className="shrink-0 text-xs text-ink-soft">Drag to pan. Select a concept for its sources. Reset view fits the whole map.</p>
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col gap-2 sm:flex-row">
      <div ref={viewport} className="min-h-[240px] min-w-0 flex-1 overflow-hidden border border-line bg-panel" style={{ touchAction: 'none' }}>
        <svg role="group" aria-label="Document concept map" width="100%" height="100%" viewBox={`0 0 ${size.width} ${size.height}`}
          className="block h-full min-h-[240px] w-full cursor-grab active:cursor-grabbing" data-zoom={zoom}
          onPointerDown={e => {
            if ((e.target as Element).closest('[role="button"]')) return
            drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y }
            e.currentTarget.setPointerCapture?.(e.pointerId)
          }}
          onPointerMove={e => { if (drag.current) setPan({ x: drag.current.px + e.clientX - drag.current.x, y: drag.current.py + e.clientY - drag.current.y }) }}
          onPointerUp={() => { drag.current = null }} onPointerCancel={() => { drag.current = null }}>
          <g transform={`translate(${pan.x + (size.width - layout.width * zoom) / 2},${pan.y + (size.height - layout.height * zoom) / 2}) scale(${zoom})`}>
            {edges.map(edge => {
              const from = layout.positions.get(edge.source), to = layout.positions.get(edge.target)
              if (!from || !to) return null
              const right = to.x >= from.x, x1 = from.x + (right ? mapCardWidth : 0), x2 = to.x + (right ? 0 : mapCardWidth)
              const y1 = from.y + mapCardHeight / 2, y2 = to.y + mapCardHeight / 2, middle = (x1 + x2) / 2
              return <path key={`${edge.source}:${edge.target}:${edge.relation}`} d={`M${x1},${y1} C${middle},${y1} ${middle},${y2} ${x2},${y2}`} fill="none" stroke="currentColor" strokeWidth="1.2" vectorEffect="non-scaling-stroke" opacity=".3"><title>{edge.relation.replaceAll('_', ' ')}</title></path>
            })}
            {nodes.map(node => {
              const p = layout.positions.get(node.id)!, words = node.label.match(/.{1,25}(?:\s|$)|.{1,25}/g) || [node.label]
              return <g key={node.id} role="button" tabIndex={0} aria-label={node.label} aria-pressed={selected?.id === node.id}
                onClick={() => setSelected(node)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(node) } }}
                className="cursor-pointer text-ink focus-visible:outline-2 focus-visible:outline-brand" transform={`translate(${p.x},${p.y})`}>
                <title>{node.label}</title><rect width={mapCardWidth} height={mapCardHeight} rx="4" className={selected?.id === node.id ? 'fill-brand/15 stroke-brand' : 'fill-paper stroke-ink-soft'} />
                <text x="10" y="25" fill="currentColor" fontSize="13">{words.slice(0, 2).map((word, i) => <tspan key={i} x="10" dy={i ? 18 : 0}>{word.trim()}{i === 1 && words.length > 2 ? '…' : ''}</tspan>)}</text>
              </g>
            })}
          </g>
        </svg>
      </div>
      {(selected || sourcePanel) && <aside aria-label="Map details" className="max-h-[35%] shrink-0 overflow-y-auto border border-line bg-paper p-3 sm:max-h-none sm:w-72">
        {selected && <><div className="flex items-start justify-between gap-2"><h3 className="break-words font-medium">{selected.label}</h3><button className={toolButton} aria-label="Close concept details" onClick={() => setSelected(null)}>×</button></div>
          {selected.explanation && <p className="mt-2 text-sm leading-relaxed">{selected.explanation}</p>}
          <p className="mt-2 text-xs text-ink-soft">{edges.filter(e => e.target === selected.id).map(e => e.relation.toLowerCase().replaceAll('_', ' ')).join(' · ')}</p>
          {selected.sourceChunkIds.length > 0 && <SourceLink source={selected} onSource={onSource} />}
        </>}
        {sourcePanel}
      </aside>}
    </div>
  </div>

  return fullscreen ? createPortal(<section ref={dialog} role="dialog" aria-modal="true" aria-label="Fullscreen mind map" className="fixed inset-0 z-[200] flex min-h-0 flex-col bg-paper p-3 text-ink sm:p-4">{content}</section>, document.body)
    : <div className="flex min-h-[320px] flex-1 flex-col" style={{ height: '100%' }}>{content}</div>
}
