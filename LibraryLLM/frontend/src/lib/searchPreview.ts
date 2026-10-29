import {useEffect,useState} from 'react'
import {request} from './api'
import {useAuthStore} from '../store/useAuthStore'
import type {SearchInterpretation,SearchMode} from './searchNlu'
import type {DisplayBook,CatalogueSource} from './libraryCatalogue'

export type PreviewOperation={operation_id:string;kind:string;label:string;field?:string;input_type?:'text'|'number'|'select';options?:string[]}
export type PreviewResponse={results:DisplayBook[];source?:CatalogueSource;has_more:boolean;offset:number;limit:number;
  total:number|null;total_ranked_candidates?:number;coverage?:{kind:string;complete:boolean;notice:string};interpretation:SearchInterpretation;
  preview:{state_id:string;accepted_plan_version:number;original_query:string;accepted_query:string;parser_version:string;
    source_digest:string;ir_digest:string;expires_at:string;mode:SearchMode;operations:PreviewOperation[];decision:string;message:string;advisory?:string|null}}

/** A URL requests the preview; only the authenticated server can enable it. */
export function useSearchPreviewGate(requested:boolean) {
  const token=useAuthStore(s=>s.token),key=`${requested}:${token}`
  const [result,setResult]=useState<{key:string;enabled:boolean}|null>(null)
  useEffect(()=>{
    if(!requested||!token)return
    const controller=new AbortController()
    void request<{smart_preview:boolean}>('/search-api/query/features',{signal:controller.signal})
      .then(value=>{if(!controller.signal.aborted)setResult({key,enabled:value.smart_preview===true})})
      .catch(()=>{if(!controller.signal.aborted)setResult({key,enabled:false})})
    return()=>controller.abort()
  },[requested,token,key])
  return {enabled:requested&&result?.key===key&&result.enabled,pending:requested&&!!token&&result?.key!==key}
}
