import {useEffect,useState} from 'react'
import {Link} from 'react-router-dom'
import {Modal} from './StaffUI'
import {StatePanel} from './WorkspaceUI'
import {BookEditor} from '../pages/LibraryInventory'
import {LibraryStockEditor} from './LibraryStockEditor'
import {AddSoftCopyModal} from '../pages/LibraryAssets'
import {assetPath} from '../lib/libraryAssets'
import {institutionApi} from '../lib/institutions'
import {inventoryBase,type LibraryBook} from '../lib/libraryInventory'
import type {Availability} from '../lib/libraryLending'
import {useAuthStore} from '../store/useAuthStore'
import {catalogueChanged} from '../lib/catalogueInvalidation'

/** Existing canonical management forms, embedded in the shared book detail. */
export function StaffBookManagement({libraryId,bookId,changed}:{libraryId:string;bookId:string;changed:()=>void}) {
  const token=useAuthStore(s=>s.token),[revision,setRevision]=useState(0),key=`${libraryId}:${bookId}:${token}:${revision}`
  const [result,setResult]=useState<{key:string;row?:LibraryBook & {availability?:Availability};error?:string}|null>(null),[action,setAction]=useState<'edit'|'stock'|'online'|null>(null)
  useEffect(()=>{let alive=true;const controller=new AbortController();void institutionApi<LibraryBook & {availability?:Availability}>(`${inventoryBase(libraryId)}/books/${bookId}`,'GET',undefined,controller.signal).then(row=>{if(alive)setResult({key,row})}).catch(reason=>{if(alive&&!controller.signal.aborted)setResult({key,error:reason instanceof Error?reason.message:'Unable to load book management.'})});return()=>{alive=false;controller.abort()}},[libraryId,bookId,key])
  const row=result?.key===key?result.row:undefined,error=result?.key===key?result.error:undefined
  const saved=()=>{setAction(null);setRevision(v=>v+1);catalogueChanged(libraryId);changed()}
  if(error)return <StatePanel title="Book management unavailable" kind="error">{error}</StatePanel>
  if(!row)return <p role="status">Loading book management…</p>
  return <section aria-label="Staff book management">
    {row.holding&&<dl className="book-facts"><div><dt>Physical stock</dt><dd>{row.holding.total_copies}</dd></div><div><dt>Requestable quantity</dt><dd>{row.availability?.requestable??'Circulation setup required'}</dd></div></dl>}
    <div className="catalogue-actions"><button className="ui-button ui-secondary" disabled={row.status!=='ACTIVE'} onClick={()=>setAction('edit')}>Edit Book</button><button className="ui-button ui-secondary" disabled={row.status!=='ACTIVE'} onClick={()=>setAction('stock')}>{row.holding?'Manage Stock':'Add Physical Stock'}</button><button className="ui-button ui-secondary" disabled={row.status!=='ACTIVE'} onClick={()=>setAction('online')}>Add Online Copy</button><Link className="ui-button ui-secondary" to={assetPath(libraryId,true)+`?book=${encodeURIComponent(bookId)}`}>Manage Online Copy</Link></div>
    {action==='edit'&&<Modal title={`Edit Book · ${row.accession_number}`} onClose={()=>setAction(null)}><div className="institutions inventory-dialog"><BookEditor libraryId={libraryId} initial={row} onSaved={saved}/></div></Modal>}
    {action==='stock'&&<Modal title={`Manage Stock · ${row.accession_number}`} onClose={()=>setAction(null)}><div className="institutions inventory-dialog"><LibraryStockEditor libraryId={libraryId} row={row} saved={saved}/></div></Modal>}
    {action==='online'&&<AddSoftCopyModal libraryId={libraryId} bookId={bookId} bookTitle={row.title} close={()=>setAction(null)} saved={saved}/>}</section>
}
