import { useEffect, useState, type FormEvent } from 'react'
import { coreRequest } from '../lib/api'
import { date, Feedback, Modal, Pager, Panel, Table } from '../components/StaffUI'

interface StaffUser {
  user_id: number; name: string; email: string; role: 'ADMIN' | 'LIBRARIAN';
  is_email_verified: boolean; is_active: boolean; created_at: string;
}
interface StaffDirectory { users: StaffUser[]; count: number; librarian_count: number }

export function StaffManagement({ onCount }: { onCount: (count: number | null) => void }) {
  const [data, setData] = useState<StaffDirectory>({ users: [], count: 0, librarian_count: 0 })
  const [page, setPage] = useState(0), [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<{ error: boolean; text: string } | null>(null)
  const [editor, setEditor] = useState<StaffUser | 'new' | null>(null)
  const [confirm, setConfirm] = useState<StaffUser | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    coreRequest<StaffDirectory>(`/staff/?limit=20&offset=${page * 20}`, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) { setData(result); onCount(result.librarian_count) } })
      .catch(reason => { if (!controller.signal.aborted) { setError(reason.message); onCount(null) } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [page, revision, onCount])
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = new FormData(event.currentTarget)
    setBusy(true); setFeedback(null)
    try {
      if (editor === 'new') {
        const result = await coreRequest<{ user: StaffUser; verification_sent: boolean }>('/staff/librarians', {
          method: 'POST', body: JSON.stringify({ name: String(form.get('name')).trim(), email: String(form.get('email')).trim() }),
        })
        setFeedback({ error: !result.verification_sent, text: result.verification_sent
          ? 'Librarian created. A verification code was emailed. Share the setup address privately.'
          : 'Librarian created, but the verification email could not be sent. Use Resend verification after checking email delivery.' })
      } else if (editor) {
        await coreRequest(`/staff/${editor.user_id}`, { method: 'PATCH', body: JSON.stringify({ name: String(form.get('name')).trim() }) })
        setFeedback({ error: false, text: 'Librarian name updated.' })
      }
      setEditor(null); setRevision(v => v + 1)
    } catch (reason) {
      setFeedback({ error: true, text: reason instanceof Error ? reason.message : 'Unable to save staff account.' })
    } finally { setBusy(false) }
  }
  async function statusChange() {
    if (!confirm || busy) return
    setBusy(true); setFeedback(null)
    try {
      await coreRequest(`/staff/${confirm.user_id}`, { method: 'PATCH', body: JSON.stringify({ is_active: !confirm.is_active }) })
      setFeedback({ error: false, text: confirm.is_active ? 'Librarian disabled. Existing tokens will be rejected.' : 'Librarian enabled.' })
      setConfirm(null); setRevision(v => v + 1)
    } catch (reason) { setFeedback({ error: true, text: reason instanceof Error ? reason.message : 'Unable to change account status.' }) }
    finally { setBusy(false) }
  }
  async function resend(user: StaffUser) {
    if (busy) return
    setBusy(true); setFeedback(null)
    try {
      await coreRequest(`/staff/${user.user_id}/resend-verification`, { method: 'POST' })
      setFeedback({ error: false, text: 'Verification code sent.' })
    } catch (reason) { setFeedback({ error: true, text: reason instanceof Error ? reason.message : 'Unable to send verification.' }) }
    finally { setBusy(false) }
  }
  return <>
    <Feedback value={feedback} />
    <Panel title="Staff management" tools={<button className="staff-primary" disabled={busy} onClick={() => { setEditor('new'); setFeedback(null) }}>Create Librarian</button>}>
      <p className="staff-note">Staff accounts only. Librarians choose their own passwords using the emailed verification code at <code>/staff/setup</code>. Share that address privately. Existing unverified accounts can use their original email verification flow. Administrator creation and recovery remain local operator tasks.</p>
      {error ? <div role="alert" className="staff-feedback is-error">{error} <button onClick={() => setRevision(v => v + 1)}>Retry</button></div> : loading ? <p role="status" className="staff-empty">Loading staff…</p> : <>
        <Table headers={['Name', 'Email', 'Role', 'Verification', 'Status', 'Created', 'Actions']} count={data.users.length} empty="No staff accounts found.">
          {data.users.map(user => <tr key={user.user_id}>
            <td>{user.name}</td><td>{user.email}</td><td>{user.role}</td><td>{user.is_email_verified ? 'Verified' : 'Pending'}</td><td>{user.is_active ? 'Active' : 'Disabled'}</td><td>{date(user.created_at)}</td>
            <td>{user.role === 'LIBRARIAN' ? <>
              <button disabled={busy} onClick={() => { setEditor(user); setFeedback(null) }}>Edit name</button>
              <button disabled={busy} onClick={() => { setConfirm(user); setFeedback(null) }}>{user.is_active ? 'Disable' : 'Enable'}</button>
              {!user.is_email_verified && <button disabled={busy || !user.is_active} onClick={() => void resend(user)}>Resend verification</button>}
            </> : <span className="staff-muted">Managed locally</span>}</td>
          </tr>)}
        </Table><Pager page={page} count={data.count} onChange={setPage} />
      </>}
    </Panel>
    {editor && <Modal title={editor === 'new' ? 'Create Librarian' : 'Edit librarian name'} busy={busy} onClose={() => setEditor(null)}>
      <Feedback value={feedback} />
      <form onSubmit={save} className="staff-form">
        <label className="wide">Name<input name="name" required maxLength={120} defaultValue={editor === 'new' ? '' : editor.name} disabled={busy} /></label>
        {editor === 'new' && <label className="wide">Email<input name="email" type="email" required autoComplete="off" disabled={busy} /></label>}
        {editor === 'new' && <p className="wide">This sends an email verification code. No password is entered or shared by the administrator.</p>}
        <footer><button type="button" disabled={busy} onClick={() => setEditor(null)}>Cancel</button><button type="submit" className="staff-primary" disabled={busy}>{busy ? 'Saving…' : editor === 'new' ? 'Create and send code' : 'Save name'}</button></footer>
      </form>
    </Modal>}
    {confirm && <Modal title={`${confirm.is_active ? 'Disable' : 'Enable'} librarian?`} busy={busy} onClose={() => setConfirm(null)}>
      <p>{confirm.name} — {confirm.email}</p><p className="my-4">{confirm.is_active ? 'This blocks sign-in and rejects existing tokens on subsequent authenticated requests.' : 'This restores access, subject to email verification and password setup.'}</p>
      <Feedback value={feedback} /><div className="staff-confirm-actions"><button disabled={busy} onClick={() => setConfirm(null)}>Cancel</button><button className="staff-primary" disabled={busy} onClick={() => void statusChange()}>{busy ? 'Updating…' : 'Confirm'}</button></div>
    </Modal>}
  </>
}
