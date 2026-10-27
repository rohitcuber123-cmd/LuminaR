import {useState} from 'react'
import {useAuthStore} from '../store/useAuthStore'
import {request} from '../lib/api'
import {searchContext,personalizedSearch,setPersonalizedSearch,forgetSearch,type SearchScope} from '../lib/searchContext'

export function useSearchContext(scope:SearchScope={}) {
  useAuthStore(s=>s.token)
  const [revision,refresh]=useState(0),[error,setError]=useState('')
  const current=searchContext(scope),personalized=personalizedSearch()
  async function clear() {
    const params=new URLSearchParams()
    if(scope.libraryId){params.set('library_id',scope.libraryId);params.set('staff',String(!!scope.staff))}
    try {
      await request(`/api/search-context/${current.id}?${params}`,{method:'DELETE'})
      // The caller clears its route in the same completion. Do not rerender the
      // old query with a new identifier before that navigation has completed.
      forgetSearch(scope);setError('');return true
    } catch {
      setError('Unable to clear the server search context. Please retry.');return false
    }
  }
  return {...current,revision,personalized,error,clear,
    toggle:(value:boolean)=>{setPersonalizedSearch(value);refresh(v=>v+1)}}
}
