import type {KGNode,KGEdge} from '../lib/knowledgeGraph'
const colour:Record<string,string>={book:'#235344',author:'#ad663b',subject:'#67628c',topic:'#59789b'}
export function MetadataGraphCanvas({nodes,edges,selected,onSelect,zoom=1}:{nodes:KGNode[];edges:KGEdge[];selected:KGNode|null;onSelect:(node:KGNode)=>void;zoom?:number}) {
  const features=nodes.filter(node=>node.kind!=='book'),books=nodes.filter(node=>node.kind==='book'&&!node.seed)
  const height=Math.max(460,features.length*45+70,books.length*55+70)
  const position=(node:KGNode)=>node.seed?{x:135,y:height/2}:node.kind==='book'?{x:765,y:45+books.indexOf(node)*(height-90)/Math.max(1,books.length-1)}:{x:450,y:45+features.indexOf(node)*(height-90)/Math.max(1,features.length-1)}
  const map=new Map(nodes.map(n=>[n.id,n])),nodeColour=(kind:string)=>colour[kind]||'#777068'
  return <svg viewBox={`0 0 900 ${height}`} width={900*zoom} height={height*zoom} className="max-w-none" aria-label="Select a book, author or subject to inspect its links">
    {edges.map(edge=>{const source=map.get(edge.source),target=map.get(edge.target);if(!source||!target)return null;const a=position(source),b=position(target),focus=selected&&(edge.source===selected.id||edge.target===selected.id);return <path key={`${edge.source}:${edge.target}`} d={`M ${a.x} ${a.y} C ${(a.x+b.x)/2} ${a.y}, ${(a.x+b.x)/2} ${b.y}, ${b.x} ${b.y}`} fill="none" stroke={focus?nodeColour(target.kind):'#d5ddd5'} strokeWidth={focus?3:1.3} opacity={selected && !focus ? .25 : 1}/>})}
    {nodes.map(node=>{const p=position(node);return <g key={node.id} role="button" tabIndex={0} aria-label={`Inspect ${node.kind}: ${node.label}`} onClick={()=>onSelect(node)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(node)}}} style={{cursor:'pointer'}}><title>{node.label}</title><rect x={p.x-115} y={p.y-17} width={230} height={34} rx={node.kind==='book'?8:17} fill={selected?.id===node.id||node.seed?nodeColour(node.kind):'#f8f7f0'} stroke={nodeColour(node.kind)} strokeWidth={selected?.id===node.id?2.5:1}/><text x={p.x} y={p.y+4} textAnchor="middle" fontSize={12} fill={selected?.id===node.id||node.seed?'#fff':nodeColour(node.kind)}>{node.label.length>32?node.label.slice(0,31)+'…':node.label}</text></g>})}
  </svg>
}
