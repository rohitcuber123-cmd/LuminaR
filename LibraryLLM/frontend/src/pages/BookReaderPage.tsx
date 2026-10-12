import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useProductContext } from '../hooks/useProductContext'
import { productBookPath } from '../lib/productContext'
import { getReadableBook, type ReadableBook } from '../lib/api'
import { useAuthStore } from '../store/useAuthStore'
import { StatePanel } from '../components/WorkspaceUI'
export function BookReaderPage() {
  const { workId='' }=useParams(),context=useProductContext(),token=useAuthStore(s=>s.token)
  const [revision,setRevision]=useState(0),key=`${workId}:${token}:${revision}`
  const [result,setResult]=useState<{key:string;book?:ReadableBook;error?:string}|null>(null)
  useEffect(()=>{let alive=true;void getReadableBook(workId).then(book=>{if(alive)setResult({key,book})}).catch(reason=>{if(alive)setResult({key,error:reason instanceof Error?reason.message:'Unable to load this book.'})});return()=>{alive=false}},[workId,key])
  const current=result?.key===key ? result : null
  return <article className="mx-auto max-w-3xl px-6 py-12"><Link className="text-sm text-brand" to={context.personalPath(productBookPath(workId,context.libraryId))}>← Back to book</Link>
    {current?.error ? <StatePanel title="Unable to load this book" kind="error" action={<button className="assistant-button" onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{current.error}</StatePanel> : !current?.book ? <p className="mt-8 text-ink-soft" role="status">Loading full text…</p> : <><h1 className="mt-8 font-display text-3xl text-ink">{current.book.title}</h1><p className="mt-2 text-ink-soft">{current.book.authors.join(', ')}</p><div className="mt-10 whitespace-pre-wrap font-serif text-lg leading-8 text-ink">{current.book.text}</div></>}
  </article>
}
