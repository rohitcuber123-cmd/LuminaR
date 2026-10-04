import { Link } from 'react-router-dom'
import type { ReasonPath } from '@/lib/knowledgeGraph'

const colours: Record<string, string> = { author: '#ad663b', subject: '#67628c', topic: '#59789b' }
const labels: Record<string, string> = { author: 'Author', subject: 'Subject', topic: 'Description topic', series: 'Series', publisher: 'Publisher', language: 'Language', era: 'Publication era' }
const shorten = (value: string, length: number) => value.length > length ? `${value.slice(0, length - 1)}…` : value

export function BookConnectionGraph({ paths, seedTitle, bookTitle }: { paths: ReasonPath[]; seedTitle?: string; bookTitle?: string }) {
  const first = paths[0]
  const source = first?.nodes[0]
  const target = first?.nodes[2]
  const features = [...new Map(paths.filter(path => path.nodes.length === 3 && path.nodes[0] === source && path.nodes[2] === target)
    .map(path => [path.nodes[1], path])).values()]
  if (!source || !target || !features.length) return <p className="mt-3 text-xs text-ink-soft">No connection map is available for this book.</p>
  const starting = seedTitle || source
  const related = bookTitle || target
  const height = 160 + features.length * 64
  return <figure className="mt-3 min-w-0 rounded-sm border border-line bg-white/40 p-3" aria-label={`Knowledge graph connection to ${related}`}>
    <figcaption className="break-words text-xs text-ink-soft"><span className="font-semibold text-moss">{starting}</span> → shared relationships → <span className="font-semibold text-moss">{related}</span></figcaption>
    <svg viewBox={`0 0 360 ${height}`} className="mx-auto mt-3 block w-full max-w-[360px]" role="img" aria-label={`Connection map: ${starting} to ${related}`}>
      <title>{starting} connected to {related}</title>
      <desc>{features.map(path => `${starting} → ${labels[path.kind] ?? path.kind}: ${path.label} → ${related}`).join('. ')}</desc>
      {features.map((path, index) => {
        const y = 110 + index * 64
        const colour = colours[path.kind] ?? '#777068'
        return <g key={`edges:${path.nodes[1]}`} stroke={colour} fill="none" strokeWidth={1.5}>
          <path d={`M 180 58 C 14 58, 14 ${y}, 54 ${y}`} />
          <path d={`M 306 ${y} C 346 ${y}, 346 ${height - 58}, 180 ${height - 58}`} />
        </g>
      })}
      {[{ id: source, title: starting, y: 38 }, { id: target, title: related, y: height - 38 }].map(node => <g key={node.id}>
        <title>{node.title} ({node.id})</title>
        <rect x={32} y={node.y - 20} width={296} height={40} rx={5} fill="#235344" />
        <text x={180} y={node.y + 4} textAnchor="middle" fontSize={12} fill="white">{shorten(node.title, 40)}</text>
      </g>)}
      {features.map((path, index) => {
        const y = 110 + index * 64
        const colour = colours[path.kind] ?? '#777068'
        return <g key={path.nodes[1]}>
          <title>{labels[path.kind] ?? path.kind}: {path.label}</title>
          <rect x={54} y={y - 24} width={252} height={48} rx={14} fill="#f8f7f0" stroke={colour} />
          <text x={180} y={y - 6} textAnchor="middle" fontSize={10} fill={colour}>{labels[path.kind] ?? path.kind}</text>
          <text x={180} y={y + 11} textAnchor="middle" fontSize={12} fill="#235344">{shorten(path.label, 34)}</text>
        </g>
      })}
    </svg>
    <p className="mt-2 text-xs text-ink-soft">Only the verified relationships between these two books are shown. Full labels appear in Why related?</p>
    <Link to={`/experimental/kg?seed=${encodeURIComponent(target)}`} className="mt-3 inline-block text-xs text-moss underline">Explore this book in Graph Lab →</Link>
  </figure>
}
