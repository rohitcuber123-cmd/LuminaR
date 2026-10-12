import { useProductContext } from '../hooks/useProductContext'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getNewArrivals, type BackendBook } from '../lib/api'
import { globalBookPresentation } from '../lib/bookPresentation'
import { BookCard } from './BookCard'
import { BookCarousel } from './BookCarousel'
import { useHomeCatalogue, homeCataloguePath } from './HomeCatalogueContext'
export function NewArrivals() {
  const context=useHomeCatalogue(),[books,setBooks]=useState<BackendBook[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(false)
  const productNavigation=useProductContext()
  useEffect(()=>{if(context)return;let alive=true;void getNewArrivals(12).then(rows=>{if(alive)setBooks(rows)}).catch(()=>{if(alive)setError(true)}).finally(()=>{if(alive)setLoading(false)});return()=>{alive=false}},[context])
  const rows=context ? context.data.new_arrivals : books.map(globalBookPresentation)
  return <section id="new-arrivals" className="mx-auto max-w-[90rem] px-6 py-16 md:px-10 md:py-20">
    <div className="mb-10 flex items-end justify-between border-b border-line pb-6"><h2 className="font-display text-[clamp(1.6rem,3.4vw,2.3rem)] text-ink">New Arrivals</h2><Link to={productNavigation.personalPath(homeCataloguePath(context,'new-arrivals'))} className="font-display shrink-0 text-[0.75rem] tracking-wide text-brand hover:underline">View all</Link></div>
    {!context && loading ? <BookCarousel>{Array.from({length:12},(_,i)=><div className="w-[180px] shrink-0 animate-pulse" key={i}><div className="aspect-[2/3] rounded-[2px] bg-line" /></div>)}</BookCarousel> : !context && error ? <p role="alert">Unable to load new arrivals.</p> : !rows.length ? <p>No new arrivals available.</p> :
    <BookCarousel>{rows.map(book=><div className="w-[180px] shrink-0" key={book.display_id}><BookCard book={book} changed={context?.changed} rail />{book.added_at && Number.isFinite(Date.parse(book.added_at)) && <p className="mt-3 text-xs text-ink-soft">Added {new Date(book.added_at).toLocaleDateString(undefined,{month:'short',year:'numeric'})}</p>}</div>)}</BookCarousel>}
  </section>
}
