import {useEffect,useState} from 'react'
import {request} from '../lib/api'
import {institutionApi} from '../lib/institutions'
import {catalogueBase} from '../lib/libraryCatalogue'
import {useAuthStore} from '../store/useAuthStore'
import type {SearchFacets} from '../lib/searchNlu'

export function useSearchFacets(libraryId:string|null,staff=false) {
  const token=useAuthStore(s=>s.token),key=`${token}:${libraryId}:${staff}`
  const [result,setResult]=useState<{key:string;data:SearchFacets}|null>(null)
  useEffect(()=>{
    if(!token)return
    const controller=new AbortController()
    const promise=libraryId?institutionApi<SearchFacets>(`${catalogueBase(libraryId)}/facets?staff=${staff}`,'GET',undefined,controller.signal):request<SearchFacets>('/search-api/facets',{signal:controller.signal})
    void promise.then(data=>{if(!controller.signal.aborted&&data?.capabilities&&Array.isArray(data.results))setResult({key,data})}).catch(()=>{})
    return()=>controller.abort()
  },[key,token,libraryId,staff])
  return result?.key===key?result.data:null
}
