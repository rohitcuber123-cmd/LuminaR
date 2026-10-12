import { useEffect,useState } from 'react'
import { Link } from 'react-router-dom'
import { getReadingList } from '../lib/api'
import { globalDisplayBook, type DisplayBook } from '../lib/libraryCatalogue'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { useProductContext } from '../hooks/useProductContext'
import { BookCard } from '../components/BookCard'
import { CatalogueSurface,CatalogueGrid } from '../components/CatalogueSurface'
import { StatePanel } from '../components/WorkspaceUI'
import { showToast } from '../components/Toast'
type SavedBook={target_key?:string;work_id?:string;target_type?:string;library_id?:string;library_book_id?:string;title:string;authors:string|string[];subjects?:string|string[];cover_url?:string;accessible?:boolean;book_id?:number}
export function ReadingListPage() {
  const context=useProductContext(),token=useAuthStore(s=>s.token),readingList=useLibraryStore(s=>s.readingList),remove=useLibraryStore(s=>s.removeFromList)
  const [revision,setRevision]=useState(0),key=`${token}:${readingList.join('|')}:${revision}`
  const [result,setResult]=useState<{key:string;items:SavedBook[];error?:string}|null>(null),[busy,setBusy]=useState<string|null>(null)
  useEffect(()=>{let alive=true;void getReadingList().then(r=>{if(alive)setResult({key,items:r.items || []})}).catch(e=>{if(alive)setResult({key,items:[],error:e instanceof Error ? e.message : 'Unable to load reading list.'})});return()=>{alive=false}},[key])
  const current=result?.key===key ? result : null
  async function removeUnavailable(target:string){setBusy(target);try{await remove(target)}catch(e){if(token===useAuthStore.getState().token)showToast(e instanceof Error?e.message:'Unable to remove saved book.','warning',{scope:token || undefined})}finally{setBusy(null)}}
  return <CatalogueSurface title="My Reading List" description={current ? `${current.items.length} books saved for later.` : 'Your personal saved books.'} loading={!current} error={current?.error} retry={()=>setRevision(v=>v+1)}
    empty={current && !current.items.length && <StatePanel title="Nothing here yet" action={<Link className="ui-button" to={context.cataloguePath}>Browse Catalog</Link>}>Add books from the catalogue to your reading list.</StatePanel>}>
    <CatalogueGrid>{current?.items.map(item=>{
      const key=item.target_key || item.work_id || '',global=globalDisplayBook({work_id:item.work_id,book_id:item.book_id,title:item.title,authors:Array.isArray(item.authors)?item.authors.join('; '):item.authors,subjects:Array.isArray(item.subjects)?item.subjects.join('|'):item.subjects,cover_url:item.cover_url},context.libraryId || '')
      const book:DisplayBook=item.target_type==='LIBRARY_BOOK' ? {...global,display_id:item.library_book_id || key,library_id:item.library_id || '',library_book_id:item.library_book_id || null,global_work_id:null,source:'LIBRARY'} : global
      return item.accessible===false ? <article key={key}><StatePanel title="Unavailable library book">Your library membership or this record is no longer available.</StatePanel><button className="assistant-button" disabled={busy===key} onClick={()=>void removeUnavailable(key)}>Remove from Reading List</button></article> : <BookCard key={key} book={book} />
    })}</CatalogueGrid>
  </CatalogueSurface>
}
