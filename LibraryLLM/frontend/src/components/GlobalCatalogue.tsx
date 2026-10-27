import {useSearchFacets} from '../hooks/useSearchFacets'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getBooks, getCategories, getRecommendations, searchBooks } from '../lib/api'
import { globalBookPresentation, recommendationPresentation, searchBookPresentation } from '../lib/bookPresentation'
import { productOffset } from '../lib/productContext'
import { searchPaging } from '../lib/searchPaging'
import { useAuthStore } from '../store/useAuthStore'
import { useAssistantPageContext } from '../hooks/useAssistantPageContext'
import type { DisplayBook, SubjectCount } from '../lib/libraryCatalogue'
import { CatalogueSurface, CatalogueGrid, CatalogueSearch, CatalogueFilters, CategoryChips } from './CatalogueSurface'
import { ProductPagination } from './ProductPagination'
import { BookCard } from './BookCard'
import { ForYou } from './ForYou'
import { StatePanel } from './WorkspaceUI'
import { SearchIntelligence } from './SearchIntelligence'
import { searchOptions,hasSearchFilters,type SearchInterpretation } from '../lib/searchNlu'
import { useSearchContext } from '../hooks/useSearchContext'
import { rememberSearch } from '../lib/searchContext'
export function GlobalCatalogue({ searchPage = false }: {searchPage?:boolean}) {
  const [params,setParams]=useSearchParams(), token=useAuthStore(s=>s.token)
  const context=useSearchContext()
  const query=params.get('q') || '',category=params.get('category') === 'All' ? '' : params.get('category') || '',author=params.get('author') || ''
  const recommended=params.get('view')==='for-you', semantic=searchPage || !!query || hasSearchFilters(params),limit=semantic ? 10 : 20
  const shouldSearch=!!query.trim()||!!category||!!author||hasSearchFilters(params)||context.active
  const facets=useSearchFacets(null)
  const offset=semantic ? searchPaging(params).offset : params.has('offset') ? productOffset(params.get('offset')) : (Math.max(1,productOffset(params.get('page')) || 1)-1)*limit
  const sort=['new_arrivals','popular'].includes(params.get('sort') || '') ? params.get('sort')! : 'catalogue'
  const [revision,setRevision]=useState(0),[subjects,setSubjects]=useState<SubjectCount[]>([])
  const key=`${params}:${token}:${revision}:${searchPage}:${context.id}:${context.personalized}`
  const [result,setResult]=useState<{key:string;books:DisplayBook[];total:number|null;more:boolean;error?:string;interpretation?:SearchInterpretation}|null>(null)
  const current=result?.key===key ? result : null,loading=!current
  useAssistantPageContext({work_ids:current?.books.map(b=>b.global_work_id || '').slice(0,4) || []})
  useEffect(()=>{let alive=true;void getCategories().then(r=>{if(alive)setSubjects(r.categories.map(c=>({subject:c.name,count:c.count})))}).catch(()=>{});return()=>{alive=false}},[])
  useEffect(()=>{
    let alive=true
    async function load() {
      if(searchPage&&!shouldSearch){if(alive)setResult({key,books:[],total:0,more:false});return}
      try {
        let books:DisplayBook[],total:number|null,more:boolean,interpretation:SearchInterpretation|undefined
        if(semantic) {
          const response=await searchBooks(query,limit,params.get('library') || 'LIB001',false,false,offset,{category,author,...searchOptions(params),session_id:context.id,personalized:context.personalized})
          interpretation=response.interpretation
          if(alive)rememberSearch({},interpretation?.session)
          books=(response.results || []).filter(b=>!!b.work_id).map(searchBookPresentation);total=response.total_ranked_candidates ?? books.length;more=response.has_more===true
        } else if(recommended) {
          const response=await getRecommendations(category || author ? 50 : limit,category || author ? 0 : offset)
          const pool=response.recommendations.map(recommendationPresentation).filter(b=>(!category || b.subjects.some(s=>s.toLowerCase()===category.toLowerCase())) && (!author || b.authors.join('; ').toLowerCase().includes(author.toLowerCase())))
          books=category || author ? pool.slice(offset,offset+limit) : pool;total=category || author ? pool.length : response.total_ranked_candidates ?? offset+books.length;more=category || author ? offset+limit<total : response.has_more===true
        } else {const response=await getBooks(limit,offset,{category,author,sort});books=response.results.map(globalBookPresentation);total=response.count;more=response.has_more ?? (total!==null && offset+books.length<total)}
        if(alive)setResult({key,books,total,more,interpretation})
      } catch(error) {if(alive)setResult({key,books:[],total:0,more:false,error:error instanceof Error ? error.message : 'Unable to load books.'})}
    }
    void load();return()=>{alive=false}
  },[key,query,category,author,offset,sort,semantic,recommended,searchPage,limit,params,context.id,context.personalized,shouldSearch])
  function update(name:string,value:string) {const next=new URLSearchParams(params);if(value) next.set(name,value); else next.delete(name);if(name==='q'&&value!==query)['category','author','rating_min','rating_max','year_min','year_max','format','availability','language','search_sort'].forEach(field=>next.delete(field));if(['q','mode'].includes(name))next.delete('omit');else if(name!=='omit'){const key=name==='category'?'subject':name;next.set('omit',(next.get('omit')||'').split(',').filter(v=>v&&v!==key&&!v.startsWith(key+'@')).join(','))}next.delete('offset');next.delete('page');setParams(next)}
  function page(value:number) {const next=new URLSearchParams(params);if(value) next.set('offset',String(value)); else next.delete('offset');next.delete('page');setParams(next)}
  async function clearContext(){if(await context.clear())setParams(new URLSearchParams())}
  function resolved(mode:string){const next=new URLSearchParams(params);next.set('mode',mode);next.set('resolved',String(Date.now()));next.delete('offset');setParams(next)}
  const rejected=!!current?.interpretation?.decision&&!['EXECUTABLE','EXECUTABLE_WITH_NOTICE'].includes(current.interpretation.decision.decision_type)
  return <CatalogueSurface title={searchPage ? 'Search' : recommended ? 'For You' : sort==='new_arrivals' ? 'New Arrivals' : sort==='popular' ? 'Popular' : 'Catalog'}
    description={semantic && query ? `Global search results for “${query}”` : recommended ? 'Your global catalogue recommendations.' : 'Explore LuminaR’s global catalogue.'}
    search={<CatalogueSearch key={query} value={query} suggestionScope={{}} label="Search by title, author or subject" onSearch={value=>{if(value)update('q',value);else void clearContext()}} mode={params.get('mode') || 'SMART'} onMode={mode=>update('mode',mode)} />}
    extra={!searchPage && !recommended && !semantic && <div className="mb-12 -mx-6 md:-mx-10"><ForYou showViewAll={false} /></div>}
    filters={<><SearchIntelligence params={params} update={update} interpretation={current?.interpretation} facets={facets} onResolved={resolved} context={{...context,clear:()=>{void clearContext()}}}/><CategoryChips subjects={subjects} selected={category} onSelect={value=>update('category',value)} /><CatalogueFilters author={author} onAuthor={value=>update('author',value)} /></>}
    loading={loading} error={current?.error} retry={()=>setRevision(v=>v+1)} count={current?.books.length ? `Showing ${offset+1}–${offset+current.books.length} ${current.total !== null ? 'of '+current.total.toLocaleString() : 'matching'} ${semantic ? 'ranked results' : 'titles'}` : undefined}
    empty={current && !current.books.length && <StatePanel title={searchPage && !query&&!category&&!author&&!hasSearchFilters(params) ? 'Search the catalogue' : (current?.interpretation?.decision?.decision_type && !['EXECUTABLE','EXECUTABLE_WITH_NOTICE'].includes(current?.interpretation?.decision?.decision_type || 'EXECUTABLE') ? 'Edit your search to continue' : 'No books match all selected filters.')}>Remove a filter above, choose another subject, or try a different topic.</StatePanel>}
    pagination={!rejected && current && (offset>0 || current.more || (semantic && !!query)) && <ProductPagination page={Math.floor(offset/limit)+1} totalPages={current.total!==null ? Math.ceil(current.total/limit) : undefined} hasMore={current.more} busy={loading || !!current.error} onPrevious={()=>page(Math.max(0,offset-limit))} onNext={()=>page(offset+limit)} nextLabel={semantic ? 'Next Results' : 'Next page'} previousLabel={semantic ? 'Previous' : 'Previous page'} />}>
    <CatalogueGrid>{current?.books.map(book=><BookCard key={book.display_id} book={book} />)}</CatalogueGrid>
  </CatalogueSurface>
}
