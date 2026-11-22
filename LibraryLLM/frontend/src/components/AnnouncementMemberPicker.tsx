import { useEffect, useId, useRef, useState } from 'react'
import { announcementApi, type AnnouncementRecipient } from '../lib/libraryAnnouncements'
import { useAuthStore } from '../store/useAuthStore'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole } from '../lib/libraryWorkspace'

export function AnnouncementMemberPicker({libraryId,token,value,onChange}:{libraryId:string;token:string;value:AnnouncementRecipient|null;onChange:(value:AnnouncementRecipient|null)=>void}) {
  const id=useId(),[query,setQuery]=useState(''),[index,setIndex]=useState(0)
  const [result,setResult]=useState<{key:string;rows:AnnouncementRecipient[];more:boolean;error:string}|null>(null)
  const change=useRef(onChange)
  useEffect(()=>{change.current=onChange},[onChange])
  const key=`${libraryId}:${token}:${query.trim()}`
  const searching=query.trim().length>=2
  const loaded=result?.key===key
  const rows=loaded?result.rows:[]
  useEffect(()=>{
    if(query.trim().length<2)return
    const controller=new AbortController()
    const current=()=>!controller.signal.aborted&&useAuthStore.getState().token===token&&useInstitutionStore.getState().session===token&&activeLibrary(useInstitutionStore.getState())?.library_id===libraryId&&libraryRole(activeLibrary(useInstitutionStore.getState()))==='ADMIN'
    const timer=window.setTimeout(()=>{
      void announcementApi(libraryId).recipients(query.trim(),controller.signal).then(response=>{
        if(!current())return
        if(response.library_id!==libraryId)throw new Error('Member search context changed. Search again.')
        setResult({key,rows:response.results,more:response.has_more,error:''})
      }).catch(reason=>{
        if(current()){setResult({key,rows:[],more:false,error:reason instanceof Error?reason.message:'Member search unavailable.'});change.current(null)}
      })
    },250)
    return()=>{window.clearTimeout(timer);controller.abort()}
  },[libraryId,token,query,key])
  function select(member:AnnouncementRecipient){onChange(member);setQuery('');setIndex(0)}
  return <section className="announcement-picker" aria-label="Selected announcement recipient">
    {value?<div role="status" className="announcement-recipient"><strong>Selected member: {value.name}</strong><span>{value.email}</span><small>Account {value.user_id}</small><button type="button" className="ui-button ui-secondary" onClick={()=>{onChange(null);setQuery('')}}>Clear selection</button></div>:<p role="status">Select one eligible member. This sends an in-app notification.</p>}
    <label htmlFor={id}>Find member by name or email</label>
    <input id={id} role="combobox" aria-autocomplete="list" aria-expanded={searching&&loaded&&rows.length>0} aria-controls={`${id}-results`} aria-activedescendant={searching&&rows[index]?`${id}-${rows[index].user_id}`:undefined} aria-describedby={`${id}-help`} autoComplete="off" maxLength={120} value={query} onChange={e=>{setQuery(e.target.value);setIndex(0)}} onKeyDown={e=>{
      if(e.key==='Escape'&&query){e.preventDefault();e.stopPropagation();setQuery('');return}
      if(e.key==='Enter'){e.preventDefault();if(rows[index])select(rows[index])}
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setIndex(v=>rows.length?(v+(e.key==='ArrowDown'?1:rows.length-1))%rows.length:0)}
    }}/>
    <p id={`${id}-help`} className="announcement-muted">Enter at least two characters. Only eligible members of this library appear. Use arrow keys and Enter to select.</p>
    {searching&&!loaded&&<p role="status">Searching members…</p>}
    {searching&&loaded&&result.error&&<p role="alert">{result.error}</p>}
    {searching&&loaded&&!result.error&&!rows.length&&<p role="status">No eligible members found.</p>}
    <div id={`${id}-results`} role="listbox" aria-label="Eligible library members">
      {searching&&rows.map((member,i)=><div role="option" aria-selected={i===index} id={`${id}-${member.user_id}`} key={member.user_id} onMouseDown={e=>e.preventDefault()} onClick={()=>select(member)} className="announcement-member-option"><strong>{member.name}</strong><span>{member.email}</span><small>Account {member.user_id}</small></div>)}
    </div>
    {searching&&loaded&&result.more&&<p role="status">More matches available. Refine your search.</p>}
  </section>
}
