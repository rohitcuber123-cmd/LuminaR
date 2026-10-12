import { useState, type ReactNode, type FormEvent } from 'react'
import { Search, X } from 'lucide-react'
import { PageHeading, StatePanel } from './WorkspaceUI'
import type { SubjectCount } from '../lib/libraryCatalogue'
import '../styles/product.css'

export function CategoryChips({ subjects, selected = '', onSelect, label = 'Category', extra }: {
  subjects: SubjectCount[]; selected?: string; onSelect: (value: string) => void; label?: string; extra?: ReactNode
}) {
  const rows = selected && !subjects.some(s => s.subject === selected) ? [{subject:selected,count:undefined}, ...subjects] : subjects
  return <div className="category-chips" role="group" aria-label={`${label} filters`}><span>{label}:</span>
    <button type="button" aria-pressed={!selected} className={!selected ? 'is-active' : ''} onClick={() => onSelect('')}>All</button>
    {rows.map(row => <button type="button" key={row.subject} aria-pressed={selected === row.subject} className={selected === row.subject ? 'is-active' : ''}
      onClick={() => onSelect(row.subject)} title={row.subject} aria-label={row.count !== undefined ? `${row.subject} ${row.count.toLocaleString()} ${row.count === 1 ? 'book' : 'books'}` : row.subject}>{row.subject}{row.count !== undefined && <small>{row.count.toLocaleString()}</small>}</button>)}{extra}
  </div>
}
export function CatalogueSearch({ value = '', label, onSearch }: { value?: string; label: string; onSearch: (value: string) => void }) {
  const [input,setInput] = useState(value)
  function submit(event:FormEvent) { event.preventDefault();onSearch(input.trim()) }
  return <form className="product-catalogue-search" onSubmit={submit}><label className="sr-only" htmlFor="catalogue-query">{label}</label>
    <Search size={18} aria-hidden="true" /><input id="catalogue-query" type="search" maxLength={150} value={input} onChange={e=>setInput(e.target.value)} placeholder={label} />
    {input && <button type="button" className="catalogue-clear" aria-label="Clear search" onClick={()=>{setInput('');onSearch('')}}><X size={16} /></button>}
    <button type="submit" className="ui-button">Search</button>
  </form>
}
export function CatalogueGrid({ children }: { children:ReactNode }) { return <div className="product-book-grid grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">{children}</div> }
export function CatalogueFilters({ author = '', status, onAuthor, onStatus }: {author?:string; status?:string; onAuthor:(value:string)=>void; onStatus?:(value:string)=>void}) {
  return <div className="catalogue-filter-row"><label>Author<input key={author} aria-label="Filter by author" maxLength={150} defaultValue={author} onBlur={e=>{if(e.target.value.trim()!==author) onAuthor(e.target.value.trim())}} onKeyDown={e=>{if(e.key==='Enter') onAuthor(e.currentTarget.value.trim())}} /></label>
    {onStatus && <label>Circulation status<select value={status || ''} onChange={e=>onStatus(e.target.value)}><option value="">All statuses</option><option value="CIRCULATING">Circulating</option><option value="REFERENCE_ONLY">Reference Only</option><option value="TEMPORARILY_UNAVAILABLE">Temporarily unavailable</option></select></label>}</div>
}
export function CatalogueSkeleton() { return <CatalogueGrid>{Array.from({length:8},(_,i)=><div className="animate-pulse" key={i}><div className="mb-3 h-3 w-1/2 rounded bg-line" /><div className="aspect-[2/3] w-full rounded-[2px] bg-line/60" /><div className="mt-4 h-4 w-3/4 rounded bg-line" /></div>)}</CatalogueGrid> }
export function CatalogueSurface({ title,description,notice,search,filters,extra,loading,error,retry,count,children,empty,pagination }: {
  title:string; description:string; notice?:ReactNode; search?:ReactNode; filters?:ReactNode; extra?:ReactNode;
  loading:boolean; error?:string; retry:()=>void; count?:ReactNode; children:ReactNode; empty?:ReactNode; pagination?:ReactNode
}) {
  return <section className="product-catalogue mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16"><PageHeading title={title} description={description} />
    {notice}{search}{extra}{filters}
    {error ? <StatePanel title="Unable to load books" kind="error" action={<button className="ui-button" onClick={retry}>Retry</button>}>{error}</StatePanel> :
      loading ? <CatalogueSkeleton /> : <><h2 className="sr-only">Books</h2>{count && <p className="mb-6 text-[0.78rem] text-ink-soft" role="status">{count}</p>}{empty || children}{pagination}</>}
  </section>
}
