import { useEffect, useState } from 'react'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { date } from '../components/StaffUI'
import { institutionApi } from '../lib/institutions'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'

type Activity = { event_id: string; event: string; created_at: string; actor_user_id: number | null; target_user_id?: number; metadata?: { library_book_id?: string; loan_id?: string; reservation_id?: string; fee_id?: string } }
export function LibraryActivityPage() {
  const library=useInstitutionStore(activeLibrary), id=library?.library_id
  const [page,setPage]=useState(0),[revision,setRevision]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState('')
  const [data,setData]=useState<{results:Activity[];total:number}>({results:[],total:0})
  useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');setData({results:[],total:0})
    void institutionApi<typeof data>(`/libraries/${id}/staff/activity?limit=20&offset=${page*20}`,'GET',undefined,controller.signal)
      .then(result=>{if(!controller.signal.aborted)setData(result)})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason.message)})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return ()=>controller.abort()
  },[id,page,revision])
  return <div className="institutions"><PageHeading title="Operational Activity" description="Collection, lending, reservation and fee activity for this library." />{error?<StatePanel kind="error" title="Unable to load activity" action={<button onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{error}</StatePanel>:loading?<StatePanel kind="loading" title="Loading library activity…" />:<><div className="ui-table-wrap" tabIndex={0} aria-label="Operational activity"><table className="ui-table"><thead><tr><th>When</th><th>Event</th><th>Actor</th><th>Member</th><th>Reference</th></tr></thead><tbody>{data.results.map(row=><tr key={row.event_id}><td>{date(row.created_at)}</td><td>{row.event.replaceAll('_',' ')}</td><td>{row.actor_user_id?`Account #${row.actor_user_id}`:'System'}</td><td>{row.target_user_id?`Account #${row.target_user_id}`:'—'}</td><td>{row.metadata?.loan_id||row.metadata?.reservation_id||row.metadata?.fee_id||row.metadata?.library_book_id||'—'}</td></tr>)}</tbody></table></div>{!data.results.length&&<StatePanel title="No operational activity yet" />}<div className="ui-pagination"><button disabled={!page} onClick={()=>setPage(v=>v-1)}>Previous</button><span>{data.total} records · Page {page+1}</span><button disabled={(page+1)*20>=data.total} onClick={()=>setPage(v=>v+1)}>Next</button></div></>}</div>
}
