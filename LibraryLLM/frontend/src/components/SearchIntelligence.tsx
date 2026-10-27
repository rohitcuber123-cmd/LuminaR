import { LuminarSelect } from './LuminarSelect'
import type { SearchMode, SearchInterpretation, SearchFacets } from '../lib/searchNlu'
import {SearchClarification} from './SearchClarification'
import type {SearchScope} from '../lib/searchContext'

export function SearchModeControl({value='SMART',onChange}:{value?:string;onChange:(mode:SearchMode)=>void}) {
  return <label className="search-mode-control"><span className="sr-only">Search mode</span><LuminarSelect aria-label="Search mode" value={value} onChange={e=>onChange(e.target.value as SearchMode)}>
    <option value="SMART">Smart</option><option value="GENRE_SUBJECT">Genre / Subject</option><option value="TITLE_AUTHOR">Title / Author</option><option value="EXACT">Exact</option>
  </LuminarSelect></label>
}
export function SearchIntelligence({params,update,interpretation,facets,tenant=false,context,scope={},onResolved}:{params:URLSearchParams;update:(key:string,value:string)=>void;interpretation?:SearchInterpretation;facets:SearchFacets|null;tenant?:boolean;context?:{id?:string;personalized:boolean;toggle:(value:boolean)=>void;clear:()=>void;error?:string};scope?:SearchScope;onResolved?:(mode:string)=>void}) {
  const omit=(params.get('omit') || '').split(',').filter(Boolean)
  const rejected=interpretation?.decision && !['EXECUTABLE','EXECUTABLE_WITH_NOTICE'].includes(interpretation.decision.decision_type)
  return <div className="search-intelligence">
    {interpretation?.clarification&&onResolved&&<SearchClarification key={interpretation.clarification.clarification_id} clarification={interpretation.clarification} scope={scope} sessionId={context?.id} personalized={context?.personalized} onResolved={onResolved}/>}
    {context&&<div className="search-context-controls"><label><input type="checkbox" checked={context.personalized} onChange={e=>context.toggle(e.target.checked)} /> Personalized results</label><span className="text-xs">Uses books in your Reading List.</span>{interpretation?.session?.active&&<button type="button" className="ui-button ui-secondary" onClick={context.clear}>Clear search context</button>}{!rejected&&interpretation?.session?.refined&&<span role="status">Refined from previous search</span>}{context.error&&<p role="alert">{context.error}</p>}</div>}
    {interpretation&&<div className="search-query-chips" role="group" aria-label="Interpreted search">
      {interpretation.intent_label&&<span className="search-query-chip">Intent: {interpretation.intent_label}</span>}
      {interpretation.preference&&<button type="button" className="search-query-chip search-preference-chip" aria-label={`Remove ${interpretation.preference}`} onClick={()=>update('omit',[...new Set([...omit,'preference'])].join(','))}>Preference: {interpretation.preference}<span aria-hidden="true"> ×</span></button>}
      {interpretation.chips.map((chip,i)=><button type="button" className="search-query-chip" key={`${chip.key}:${i}`} aria-label={`Remove ${chip.label}`} onClick={()=>update('omit',[...new Set([...omit,chip.remove_key||chip.key])].join(','))}>{chip.label}<span aria-hidden="true"> ×</span></button>)}
      {!interpretation.clarification&&interpretation.corrections.map((c,i)=><span role="status" key={i}>{c.kind==='typo'?`Did you mean “${c.to}”? Using this canonical subject for “${c.from}”.`:`Interpreted “${c.from}” as “${c.to}”.`}</span>)}
      {!!interpretation.related_concepts?.length&&<details className="search-related-concepts"><summary>Related concepts included</summary><p>{interpretation.related_concepts.join(' · ')}</p></details>}
      {rejected?<p role="status" aria-label="Search interpretation decision">{interpretation.decision?.safe_public_message} Edit your query and search again.</p>:interpretation.notice&&<p role="status">{interpretation.notice}</p>}{!!omit.length&&<p className="text-xs">Removed constraints are excluded; your original search text is unchanged.</p>}
      {interpretation.suggested_subject&&<button type="button" onClick={()=>update(tenant?'subject':'category',interpretation.suggested_subject!)}>Search as subject: {interpretation.suggested_subject}</button>}
    </div>}
    <details className="search-filter-panel"><summary>Search filters</summary><div className="search-filter-fields">
      <label>Genre / Subject<LuminarSelect searchable aria-label="Genre / Subject filter" value={params.get(tenant?'subject':'category') || ''} onChange={e=>update(tenant?'subject':'category',e.target.value)}><option value="">All subjects</option>{facets?.results.map(row=><option key={row.subject} value={row.subject}>{row.subject}</option>)}</LuminarSelect></label>
      {facets?.capabilities.rating&&<><label>Minimum rating<input aria-label="Minimum rating" type="number" min="0" max="5" step="0.1" key={params.get('rating_min')} defaultValue={params.get('rating_min') || ''} onBlur={e=>update('rating_min',e.target.value)} /></label><label>Maximum rating<input aria-label="Maximum rating" type="number" min="0" max="5" step="0.1" key={params.get('rating_max')} defaultValue={params.get('rating_max') || ''} onBlur={e=>update('rating_max',e.target.value)} /></label></>}
      <label>Format<LuminarSelect aria-label="Format filter" value={params.get('format') || ''} onChange={e=>update('format',e.target.value)}><option value="">All formats</option>{facets?.capabilities.formats.map(fmt=><option key={fmt} value={fmt}>{fmt==='BOTH'?'Physical + Online':fmt==='ONLINE'?'Online':'Physical'}</option>)}</LuminarSelect></label>
      {facets?.capabilities.availability&&<label>Availability<LuminarSelect aria-label="Availability filter" value={params.get('availability') || ''} onChange={e=>update('availability',e.target.value)}><option value="">All availability</option><option value="AVAILABLE_NOW">Available now</option><option value="REQUESTABLE">Available to request</option></LuminarSelect></label>}
      {facets?.capabilities.year&&<><label>Published from<input aria-label="Published from" type="number" min="1000" max="2100" key={params.get('year_min')} defaultValue={params.get('year_min') || ''} onBlur={e=>update('year_min',e.target.value)} /></label><label>Published through<input aria-label="Published through" type="number" min="1000" max="2100" key={params.get('year_max')} defaultValue={params.get('year_max') || ''} onBlur={e=>update('year_max',e.target.value)} /></label></>}
      {facets?.capabilities.language&&<label>Language<input aria-label="Language filter" maxLength={60} key={params.get('language')} defaultValue={params.get('language') || ''} onBlur={e=>update('language',e.target.value.trim())} /></label>}
      <label>Sort<LuminarSelect aria-label="Search sort" value={params.get('search_sort') || 'RELEVANCE'} onChange={e=>update('search_sort',e.target.value)}><option value="RELEVANCE">Relevance</option><option value="RATING">Rating</option>{facets?.capabilities.year&&<option value="NEWEST">Newest</option>}<option value="TITLE">Title</option></LuminarSelect></label>
    </div></details>
  </div>
}
