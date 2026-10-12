"""One-time deterministic extraction; changes only the named frontend adapters."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];src=ROOT/'frontend/src'
old=(src/'components/LibraryCatalogueBook.tsx').read_text(encoding='utf8')
start=old.index('export function CatalogueBookActions(');end=old.index('\nexport function LibraryCatalogueBook(')
action=old[start:end].replace('catalogueBookPath(book)','bookPath(book)')
imports="""import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Modal } from './StaffUI'
import { patronPath } from '../lib/libraryWorkspace'
import { lendingCommand, commandKey } from '../lib/libraryLending'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { notifyBorrowChanged } from '../lib/api'
import { bookPath } from '../lib/bookPresentation'
"""
target=src/'components/CatalogueBookActions.tsx'
if not target.exists():target.write_text(imports+'\n'+action+'\n',encoding='utf8')
(src/'components/LibraryCatalogueBook.tsx').write_text("""import type { DisplayBook } from '../lib/libraryCatalogue'
import { bookSeed } from '../lib/bookPresentation'
import { patronPath } from '../lib/libraryWorkspace'
import { BookCoverArt } from './BookCoverArt'
import { BookCard } from './BookCard'
import { BookDetailView } from './BookDetailView'
import { CatalogueBookActions } from './CatalogueBookActions'
export { CatalogueBookActions } from './CatalogueBookActions'
/** Typed tenant adapters; all visual/personal composition is shared. */
export function CatalogueCover({book}: {book:DisplayBook}) {
  return <div className="catalogue-cover" aria-label={`Cover for ${book.title}`}><BookCoverArt title={book.title} author={book.authors.join('; ')} seed={bookSeed(book)} url={book.cover_url} /></div>
}
export function LibraryCatalogueBook({book,changed,detailed=false,rail=false}: {book:DisplayBook;changed:()=>void;detailed?:boolean;rail?:boolean}) {
  return detailed ? <BookDetailView book={book} backPath={patronPath(book.library_id,'catalogue')} physicalActions={<CatalogueBookActions book={book} changed={changed} />} /> : <BookCard book={book} changed={changed} rail={rail} />
}
""",encoding='utf8')
(src/'pages/BookDetailPage.tsx').write_text("""import { useState,useEffect } from 'react'
import { useParams,useSearchParams } from 'react-router-dom'
import { getBook,type BackendBook } from '../lib/api'
import { useAuthStore } from '../store/useAuthStore'
import { useAssistantPageContext } from '../hooks/useAssistantPageContext'
import { useProductContext } from '../hooks/useProductContext'
import { useMoreLikeThis } from '../hooks/useMoreLikeThis'
import { globalBookPresentation } from '../lib/bookPresentation'
import { BookDetailView,BookDetailSkeleton } from '../components/BookDetailView'
import { MoreLikeThisSection } from '../components/MoreLikeThisSection'
import { StatePanel } from '../components/WorkspaceUI'

export function BookDetailPage() {
  const {workId=''}=useParams(),[params]=useSearchParams(),context=useProductContext()
  const authenticated=useAuthStore(s=>s.isAuthenticated),token=useAuthStore(s=>s.token)
  const related=useMoreLikeThis(workId,params.get('related')==='1',authenticated)
  const [revision,setRevision]=useState(0),key=`${workId}:${token}:${revision}`
  const [result,setResult]=useState<{key:string;book?:BackendBook;error?:string}|null>(null)
  useAssistantPageContext({work_id:workId})
  useEffect(()=>{let alive=true;void getBook(workId).then(book=>{if(alive)setResult({key,book})}).catch(error=>{if(alive)setResult({key,error:error instanceof Error?error.message:'Unable to load book.'})});return()=>{alive=false}},[workId,key])
  if(result?.key!==key)return <BookDetailSkeleton />
  if(!result.book)return <section className="mx-auto max-w-[90rem] px-6 py-16"><StatePanel title="Unable to load this book" kind="error" action={<button className="ui-button" onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{result.error}</StatePanel></section>
  return <BookDetailView book={globalBookPresentation(result.book)} backPath={context.cataloguePath}
    relatedActions={<button onClick={()=>void related.load()} disabled={related.state?.status==='loading'} className="assistant-button mt-6">{related.state?.status==='loading'?'Finding related books…':'More Like This'}</button>}
    related={<MoreLikeThisSection key={workId} workId={workId} related={related} />} />
}
""",encoding='utf8')
print('Extracted canonical tenant actions and shared detail/card adapters.')
