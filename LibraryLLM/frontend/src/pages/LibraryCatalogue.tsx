import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useLibraryCatalogue } from '../hooks/useLibraryCatalogue'
import { useAssistantPageContext } from '../hooks/useAssistantPageContext'
import { useMoreLikeThis } from '../hooks/useMoreLikeThis'
import { CatalogueBookActions } from '../components/CatalogueBookActions'
import { BookCard } from '../components/BookCard'
import { BookDetailView, BookDetailSkeleton } from '../components/BookDetailView'
import { MoreLikeThisSection } from '../components/MoreLikeThisSection'
import { CatalogueSurface, CatalogueGrid, CatalogueSearch, CatalogueFilters, CategoryChips } from '../components/CatalogueSurface'
import { ProductPagination } from '../components/ProductPagination'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { patronPath } from '../lib/libraryWorkspace'
import { productOffset } from '../lib/productContext'
import { LibraryBookResources } from './LibraryAssets'
import type { CataloguePage, CatalogueDetail, GenrePage, CatalogueSource } from '../lib/libraryCatalogue'
export function CatalogueNotice({ source }: { source: CatalogueSource }) {
  return <p className="catalogue-context"><span className="ui-badge">{source.catalogue_source === 'LIBRARY_LOCAL' ? 'Library collection' : 'Global Catalogue'}</span>
    {source.catalogue_source === 'LIBRARY_LOCAL' ? `${source.local_book_count.toLocaleString()} local ${source.local_book_count === 1 ? 'book' : 'books'} in ${source.library_name}` : 'Discover LuminaR’s global catalogue. These books are not currently held by this library.'}</p>
}
export function LibraryCataloguePage({ arrivals = false, popular = false }: { arrivals?:boolean;popular?:boolean }) {
  const [params,setParams]=useSearchParams(),offset=productOffset(params.get('offset')),search=params.get('search') || '',subject=params.get('subject') || ''
  const options=new URLSearchParams(params);options.set('offset',String(offset));options.set('sort',arrivals ? 'new_arrivals' : popular ? 'popular' : params.get('sort') || 'title')
  const {library,data,loading,error,retry}=useLibraryCatalogue<CataloguePage>('books',options.toString())
  const genres=useLibraryCatalogue<GenrePage>('genres','offset=0&limit=50'),recommended=params.get('view')==='for-you'
  useAssistantPageContext({work_ids:data?.results.map(b=>b.global_work_id || '').filter(Boolean).slice(0,4) || []})
  if(!library)return <StatePanel title="Loading library…" kind="loading" />
  const fallback=data?.source.catalogue_source==='GLOBAL_FALLBACK',limit=data?.limit || 20
  function update(name:string,value:string){const next=new URLSearchParams(params);if(value) next.set(name,value); else next.delete(name);next.delete('offset');setParams(next)}
  function page(value:number){const next=new URLSearchParams(params);if(value) next.set('offset',String(value)); else next.delete('offset');setParams(next)}
  return <CatalogueSurface title={arrivals ? 'New Arrivals' : popular ? 'Popular' : recommended ? 'For You' : 'Browse Books'} description={`Explore ${fallback ? 'LuminaR’s global catalogue' : library.name+'’s collection'}.`}
    notice={data && <CatalogueNotice source={data.source} />} search={<CatalogueSearch key={`${library.library_id}:${search}`} value={search} label={fallback ? 'Search all LuminaR' : `Search ${library.name}`} onSearch={value=>update('search',value)} />}
    filters={<><CategoryChips label="Category" subjects={genres.data?.results || []} selected={subject} onSelect={value=>update('subject',value)} extra={<Link className="text-sm text-brand p-2" to={patronPath(library.library_id,'genres')}>All subjects</Link>} />
      <CatalogueFilters author={params.get('author') || ''} onAuthor={value=>update('author',value)} status={params.get('circulation_status') || ''} onStatus={fallback ? undefined : value=>update('circulation_status',value)} /></>}
    loading={loading} error={error} retry={retry} count={data?.results.length ? `${data.total !== null ? data.total.toLocaleString() : 'Matching'} books ${recommended ? 'in this recommendation set' : 'in this view'}` : undefined}
    empty={data && !data.results.length && <StatePanel title={popular ? 'No recent popularity activity' : `No matching books in ${library.name}`} action={<Link className="ui-button ui-secondary" to={`/search?q=${encodeURIComponent(search || subject || params.get('author') || '')}`}>Search all LuminaR</Link>}>Try another title, author or subject. Global discovery is a separate catalogue.</StatePanel>}
    pagination={data && <ProductPagination page={Math.floor(offset/limit)+1} totalPages={data.total!==null ? Math.ceil(data.total/limit) : undefined} hasMore={data.has_more} onPrevious={()=>page(Math.max(0,offset-limit))} onNext={()=>page(offset+limit)} />}>
    <CatalogueGrid>{data?.results.map(book=><BookCard key={book.display_id} book={book} changed={retry} />)}</CatalogueGrid>
  </CatalogueSurface>
}
export function LibraryCatalogueGenres() {
  const [params,setParams]=useSearchParams(),offset=productOffset(params.get('offset')),navigate=useNavigate()
  const {library,data,loading,error,retry}=useLibraryCatalogue<GenrePage>('genres',`offset=${offset}&limit=50`)
  return <section className="product-catalogue mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16"><PageHeading title="Genres / Subjects" description={`Discover subjects in ${library?.name || 'your library'}.`} />
    {data && <CatalogueNotice source={data.source} />}{loading ? <StatePanel title="Loading subjects…" kind="loading" /> : error ? <StatePanel title="Unable to load subjects" kind="error" action={<button onClick={retry}>Retry</button>}>{error}</StatePanel> : data && library && <>
      <CategoryChips subjects={data.results} onSelect={value=>navigate(patronPath(library.library_id,`catalogue${value ? '?subject='+encodeURIComponent(value) : ''}`))} />
      {!data.results.length && <StatePanel title="No subjects to show yet" />}<ProductPagination page={Math.floor(offset/50)+1} totalPages={Math.ceil(data.total/50)} hasMore={data.has_more} onPrevious={()=>setParams({offset:String(Math.max(0,offset-50))})} onNext={()=>setParams({offset:String(offset+50)})} />
    </>}</section>
}
export function LibraryCatalogueDetail({ global=false }: {global?:boolean}) {
  const {bookId}=useParams(),[params]=useSearchParams(),authenticated=useAuthStore(s=>s.isAuthenticated)
  const {data,library,loading,error,retry}=useLibraryCatalogue<CatalogueDetail>(global ? 'global-detail' : 'detail',`id=${encodeURIComponent(bookId || '')}`)
  const workId=data?.book.global_work_id || '',related=useMoreLikeThis(workId,params.get('related')==='1',authenticated)
  useAssistantPageContext({work_id:workId})
  if(loading)return <BookDetailSkeleton />
  if(error || !data)return <section className="mx-auto max-w-[90rem] px-6 py-16"><StatePanel title="Unable to load this book" kind="error" action={<button className="ui-button" onClick={retry}>Retry</button>}>{error}</StatePanel></section>
  return <BookDetailView book={data.book} notice={<CatalogueNotice source={data.source} />} backPath={patronPath(library?.library_id || '','catalogue')}
    resources={data.book.source === 'LIBRARY' && data.book.owned_by_current_library && data.book.library_book_id && <LibraryBookResources libraryId={data.book.library_id} bookId={data.book.library_book_id} />}
    physicalActions={<CatalogueBookActions book={data.book} changed={retry} />} relatedActions={workId && <button className="assistant-button mt-6" disabled={related.state?.status==='loading'} onClick={()=>void related.load()}>More Like This</button>}
    related={workId && <MoreLikeThisSection key={workId} workId={workId} related={related} />} />
}
