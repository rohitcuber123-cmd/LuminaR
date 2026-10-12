import type { Provenance } from '../../lib/knowledgeArtifacts'

export function SourceLink({ source, onSource }: { source: Provenance; onSource: (id: string) => void }) {
  const pages = source.sources?.filter(s => s.page && source.sourceChunkIds.includes(s.chunkId))
    .filter((s, index, all) => all.findIndex(other => other.page === s.page) === index)
    .sort((a, b) => a.page! - b.page!)
  if (pages?.length) return <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-soft">
    <span>Sources:</span>
    {pages.map(s => <button key={s.page} className="underline underline-offset-2 hover:text-brand" onClick={() => onSource(s.chunkId)}>Page {s.page}</button>)}
  </div>
  return <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
    <span>{source.pageStart ? `Page ${source.pageStart}${source.pageEnd && source.pageEnd !== source.pageStart ? `–${source.pageEnd}` : ''}` : 'Page unknown'}{source.chapter ? ` · ${source.chapter}` : ''}{source.section ? ` · ${source.section}` : ''}</span>
    {source.sourceChunkIds.slice(0, 1).map(id => <button className="underline hover:text-brand" key={id} onClick={() => onSource(id)}>View source</button>)}
  </div>
}
