import {useEffect,useLayoutEffect,useRef,useState} from 'react'
import {request,ApiError} from '../lib/api'
import {revalidateDeniedAccess} from '../lib/institutions'
import {rememberSearch,type SearchScope} from '../lib/searchContext'
import {useAuthStore} from '../store/useAuthStore'
import type {SearchClarification as Clarification,SearchInterpretation} from '../lib/searchNlu'

export function SearchClarification({clarification,scope={},sessionId,personalized=false,onResolved}:{clarification:Clarification;scope?:SearchScope;sessionId?:string;personalized?:boolean;onResolved:(mode:string)=>void}) {
  const token=useAuthStore(s=>s.token),[value,setValue]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[dismissed,setDismissed]=useState(false)
  const binding=JSON.stringify([token,scope.libraryId,!!scope.staff,sessionId,clarification.clarification_id]),live=useRef(binding)
  useLayoutEffect(()=>{live.current=binding},[binding])
  const mounted=useRef(true),controller=useRef<AbortController|null>(null)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;controller.current?.abort()}},[])
  const inputChoice=clarification.candidate_choices.find(c=>c.input_type)
  async function apply(choiceId:string,inputType?:string) {
    const ticket=binding;controller.current?.abort();controller.current=new AbortController();setBusy(true);setError('')
    try {
      const response=await request<{interpretation:SearchInterpretation}>('/search-api/query/resolve',{method:'POST',signal:controller.current.signal,body:JSON.stringify({clarification_id:clarification.clarification_id,choice_id:choiceId,query:clarification.original_query,mode:clarification.search_mode,session_id:sessionId,library_id:scope.libraryId,staff:!!scope.staff,personalized,...(inputType?{value}:{})})})
      if(!mounted.current||live.current!==ticket)return
      rememberSearch(scope,response.interpretation.session)
      // Keep keyboard focus on the persistent search input when the action
      // buttons disappear after the accepted interpretation refreshes.
      document.getElementById('catalogue-query')?.focus()
      onResolved(response.interpretation.mode)
    } catch(cause) {if(mounted.current&&live.current===ticket){setError(cause instanceof Error?cause.message:'Unable to apply this choice. Edit the query and try again.');if(scope.libraryId&&cause instanceof ApiError&&[403,404].includes(cause.status))await revalidateDeniedAccess(scope.libraryId,token)}}
    finally {if(mounted.current&&live.current===ticket)setBusy(false)}
  }
  async function dismiss() {
    setDismissed(true)
    const params=new URLSearchParams()
    if(scope.libraryId){params.set('library_id',scope.libraryId);params.set('staff',String(!!scope.staff))}
    try {await request(`/search-api/query/clarifications/${clarification.clarification_id}?${params}`,{method:'DELETE'})} catch { /* The bounded choice expires independently; accepted context is unchanged. */ }
  }
  if(dismissed)return <p role="status">Choice dismissed. Edit your query to continue.</p>
  return <section className="search-clarification" aria-label={clarification.decision_type.startsWith('EXECUTABLE')?'Search correction':'Clarify your search'} aria-busy={busy}>
    <p role="status">{clarification.question}</p>
    {inputChoice&&<label>{inputChoice.input_type==='number'?'Value':'Author name'}<input aria-label={inputChoice.input_type==='number'?'Clarification value':'Clarification author'} type={inputChoice.input_type} min={inputChoice.minimum} max={inputChoice.maximum} step={inputChoice.maximum===2100?'1':'0.1'} maxLength={100} value={value} onChange={e=>setValue(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.nativeEvent.isComposing){e.preventDefault();void apply(inputChoice.choice_id,inputChoice.input_type)}}}/></label>}
    <div className="ui-actions">{clarification.candidate_choices.map(choice=><button type="button" className="ui-button ui-secondary" key={choice.choice_id} disabled={busy||!!choice.input_type&&!value.trim()} onClick={()=>void apply(choice.choice_id,choice.input_type)}>{choice.label}</button>)}<button type="button" className="ui-button ui-ghost" disabled={busy} onClick={()=>void dismiss()}>Dismiss</button></div>
    {error&&<p role="alert">{error}</p>}
  </section>
}
