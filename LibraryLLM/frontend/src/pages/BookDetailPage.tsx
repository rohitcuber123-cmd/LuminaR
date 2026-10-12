import { useState,useEffect } from 'react'
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
