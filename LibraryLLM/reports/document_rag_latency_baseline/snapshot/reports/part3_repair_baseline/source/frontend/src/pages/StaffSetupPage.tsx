import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { StaffAuthLayout } from './StaffLoginPage'
import { coreRequest } from '../lib/api'

export function StaffSetupPage() {
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [done, setDone] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const element = event.currentTarget, form = new FormData(element)
    setError('')
    const password = String(form.get('password'))
    if (password !== form.get('confirm')) { setError('Passwords do not match.'); return }
    setBusy(true)
    try {
      await coreRequest('/auth/staff-setup', { method: 'POST', body: JSON.stringify({ email: String(form.get('email')).trim(), otp: String(form.get('otp')).trim(), password }) })
      element.reset(); setDone(true)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to complete setup.') }
    finally { setBusy(false) }
  }
  return <StaffAuthLayout>
    <h1 className="font-display text-3xl text-ink">Complete your invitation</h1>
    {done ? <div role="status" className="mt-6"><p>Your account is ready.</p><Link className="mt-5 inline-block text-brand" to="/staff/login">Sign in</Link></div> : <>
      <p className="mt-4 text-sm text-ink-soft">Use the code sent to your email by the library administrator. Codes expire after 10 minutes. Ask your administrator for a new code if needed.</p>
      {error && <p role="alert" className="mt-5 text-sm text-brand">{error}</p>}
      <form onSubmit={submit} className="mt-6 space-y-4">
        <div><label className="auth-label" htmlFor="setup-email">Email</label><input id="setup-email" className="auth-input" name="email" type="email" autoComplete="username" required disabled={busy} /></div>
        <div><label className="auth-label" htmlFor="setup-code">Verification code</label><input id="setup-code" className="auth-input" name="otp" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required disabled={busy} /></div>
        <div><label className="auth-label" htmlFor="setup-password">New password</label><input id="setup-password" className="auth-input" name="password" type="password" minLength={8} autoComplete="new-password" required disabled={busy} /></div>
        <div><label className="auth-label" htmlFor="setup-confirm">Confirm password</label><input id="setup-confirm" className="auth-input" name="confirm" type="password" minLength={8} autoComplete="new-password" required disabled={busy} /></div>
        <button type="submit" className="auth-btn" disabled={busy}>{busy ? 'Completing setup…' : 'Set password and verify'}</button>
      </form>
    </>}
  </StaffAuthLayout>
}
