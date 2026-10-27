import {useEffect,useLayoutEffect,useId,useRef,useState,type KeyboardEvent} from 'react'
import {request,ApiError} from '../lib/api'
import {revalidateDeniedAccess} from '../lib/institutions'
import {useAuthStore} from '../store/useAuthStore'
import type {SearchScope} from '../lib/searchContext'

type Suggestion={id:string;type:string;display:string;insert_text:string;match_kind:string}
export function SearchAutocomplete({value,onChange,onSelect,mode,scope={},label}:{value:string;onChange:(value:string)=>void;onSelect:(value:string)=>void;mode:string;scope?:SearchScope;label:string}) {
  const token=useAuthStore(s=>s.token),id=useId(),listId=`search-suggestions-${id}`
  const [open,setOpen]=useState(false),[active,setActive]=useState(-1),[composing,setComposing]=useState(false)
  const [result,setResult]=useState<{key:string;items:Suggestion[]}|null>(null),[error,setError]=useState('')
  const [placement,setPlacement]=useState({above:false,maxHeight:320})
  const sequence=useRef(0),selection=useRef<AbortController|null>(null),input=useRef<HTMLInputElement>(null)
  const key=JSON.stringify([token,scope.libraryId,!!scope.staff,mode,value]),live=useRef(key)
  useLayoutEffect(()=>{live.current=key},[key])
  const items=open&&!composing&&result?.key===key ? result.items : []
  useLayoutEffect(()=>{
    if(!items.length)return
    function position(){const bounds=input.current?.getBoundingClientRect();if(!bounds)return;const below=window.innerHeight-bounds.bottom-24,above=bounds.top-24;const up=below<176&&above>below;const maxHeight=Math.max(44,Math.min(420,up?above:below));setPlacement(old=>old.above===up&&old.maxHeight===maxHeight?old:{above:up,maxHeight})}
    position();window.addEventListener('resize',position);window.addEventListener('scroll',position,true)
    return()=>{window.removeEventListener('resize',position);window.removeEventListener('scroll',position,true)}
  },[items.length,key])
  useEffect(()=>{if(active>=0)document.getElementById(`${listId}-${active}`)?.scrollIntoView?.({block:'nearest'})},[active,listId])
  useEffect(()=>{
    const controller=new AbortController(),ticket=++sequence.current
    if(!open||composing||!token||mode==='EXACT'||value.trim().length<2)return()=>controller.abort()
    const timer=setTimeout(()=>{
      const params=new URLSearchParams({q:value,mode,limit:'8'})
      if(scope.libraryId){params.set('library_id',scope.libraryId);params.set('staff',String(!!scope.staff))}
      void request<{suggestions:Suggestion[]}>(`/search-api/query/suggestions?${params}`,{signal:controller.signal}).then(response=>{
        if(!controller.signal.aborted&&sequence.current===ticket&&live.current===key){setResult({key,items:response.suggestions});setActive(-1)}
      }).catch(async error=>{if(!controller.signal.aborted&&live.current===key){setResult({key,items:[]});if(scope.libraryId&&error instanceof ApiError&&[403,404].includes(error.status))await revalidateDeniedAccess(scope.libraryId,token)}})
    },200)
    return()=>{clearTimeout(timer);controller.abort()}
  },[key,open,composing,token,mode,value,scope.libraryId,scope.staff])
  useEffect(()=>{selection.current?.abort()},[key])
  useEffect(()=>()=>selection.current?.abort(),[])
  async function select(item:Suggestion) {
    const selectedKey=key,controller=new AbortController();selection.current?.abort();selection.current=controller
    setOpen(false);setError('')
    try {
      const choice=await request<{insert_text:string}>('/search-api/query/suggestions/select',{method:'POST',signal:controller.signal,body:JSON.stringify({suggestion_id:item.id,q:value,mode,library_id:scope.libraryId,staff:!!scope.staff})})
      if(controller.signal.aborted||live.current!==selectedKey)return
      onChange(choice.insert_text);onSelect(choice.insert_text);input.current?.focus()
    } catch(error) {if(!controller.signal.aborted&&live.current===selectedKey){setError('Suggestion changed. Type again or search your original wording.');if(scope.libraryId&&error instanceof ApiError&&[403,404].includes(error.status))await revalidateDeniedAccess(scope.libraryId,token)}}
  }
  function keyboard(event:KeyboardEvent<HTMLInputElement>) {
    if(composing||event.nativeEvent.isComposing)return
    if(event.key==='Escape'){event.preventDefault();setOpen(false);setActive(-1)}
    else if(items.length&&(event.key==='ArrowDown'||event.key==='ArrowUp')){
      event.preventDefault();setActive(index=>event.key==='ArrowDown'?(index+1)%items.length:(index<=0?items.length-1:index-1))
    } else if(event.key==='Enter'&&items.length&&active>=0){event.preventDefault();void select(items[active])}
    else if(event.key==='Enter'||event.key==='Tab')setOpen(false)
  }
  return <div className="search-autocomplete">
    <input ref={input} className="ui-composite-input" id="catalogue-query" type="search" role="combobox" aria-label={label} maxLength={150} value={value} autoComplete="off"
      aria-autocomplete="list" aria-expanded={!!items.length} aria-controls={items.length?listId:undefined} aria-activedescendant={active>=0&&items[active]?`${listId}-${active}`:undefined}
      onChange={e=>{onChange(e.target.value);setOpen(true);setActive(-1);setError('')}} onFocus={()=>setOpen(true)} onBlur={()=>{setOpen(false);setActive(-1)}}
      onKeyDown={keyboard} onCompositionStart={()=>setComposing(true)} onCompositionEnd={()=>setComposing(false)} placeholder={label}/>
    {!!items.length&&<ul id={listId} role="listbox" aria-label="Catalogue suggestions" className={`search-suggestions${placement.above?' is-above':''}`} style={{maxHeight:placement.maxHeight}}>{items.map((item,index)=><li key={item.id} role="presentation"><button type="button" role="option" aria-selected={index===active} id={`${listId}-${index}`} tabIndex={-1}
      onPointerDown={event=>event.preventDefault()} onMouseDown={event=>event.preventDefault()} onClick={()=>void select(item)}><span>{item.display}</span><small>{item.match_kind==='TYPO'?'Suggested correction':item.type.toLowerCase()}</small></button></li>)}</ul>}
    <span className="sr-only" role="status" aria-live="polite">{items.length?`${items.length} catalogue suggestions. Use arrow keys to choose.`:''}</span>
    {error&&<span role="status" className="search-suggestion-error">{error}</span>}
  </div>
}
