import { useEffect, useState } from 'react'
import { PageHeading, StatePanel } from '../components/WorkspaceUI'
import { StaffActivityTable, type StaffActivity } from '../components/StaffActivityTable'
import { institutionApi } from '../lib/institutions'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'

export function LibraryActivityPage() {
  const library=useInstitutionStore(activeLibrary), id=library?.library_id
  const [page,setPage]=useState(0),[revision,setRevision]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState('')
  const [data,setData]=useState<{results:StaffActivity[];total:number}>({results:[],total:0})
  useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');setData({results:[],total:0})
    void institutionApi<typeof data>(`/libraries/${id}/staff/activity?limit=20&offset=${page*20}`,'GET',undefined,controller.signal)
      .then(result=>{if(!controller.signal.aborted)setData(result)})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason.message)})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    return ()=>controller.abort()
  },[id,page,revision])
  return <div className="institutions"><PageHeading title="Operational Activity" description="Collection, lending, reservation and fee activity for this library." />{error?<StatePanel kind="error" title="Unable to load activity" action={<button onClick={()=>setRevision(v=>v+1)}>Retry</button>}>{error}</StatePanel>:loading?<StatePanel kind="loading" title="Loading library activity…" />:<StaffActivityTable data={data} page={page} onPageChange={setPage} operational />}</div>
}
