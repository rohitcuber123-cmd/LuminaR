import type { Provenance } from '../../lib/knowledgeArtifacts'

export function SourceLink({ source, onSource }: { source: Provenance; onSource: (id: string) => void }) {
  return <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-soft">
    <span>{source.pageStart ? `Page ${source.pageStart}${source.pageEnd && source.pageEnd !== source.pageStart ? `–${source.pageEnd}` : ''}` : 'Page unknown'}{source.chapter ? ` · ${source.chapter}` : ''}{source.section ? ` · ${source.section}` : ''}</span>
    {source.sourceChunkIds.slice(0, 3).map((id, index) => <button className="underline hover:text-brand" key={id} onClick={() => onSource(id)}>View source{source.sourceChunkIds.length > 1 ? ` ${index + 1}` : ''}</button>)}
  </div>
}
