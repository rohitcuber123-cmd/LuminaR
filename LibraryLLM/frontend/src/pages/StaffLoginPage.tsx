import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { BookOpen, LockKeyhole } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'

export function StaffAuthLayout({ children }: { children: ReactNode }) {
  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    return () => meta.remove()
  }, [])
  return <main className="min-h-screen bg-ink px-6 py-12 flex items-center justify-center">
    <section className="w-full max-w-md rounded-2xl border border-line bg-paper p-8 sm:p-10">
      <div className="mb-10 flex items-center gap-2 font-display text-xl text-ink"><BookOpen className="text-brand" /> LuminaR</div>
      <div className="mb-3 flex items-center gap-2 text-brand"><LockKeyhole size={18} /><span className="font-display text-sm">Staff portal</span></div>
      {children}
      <p className="mt-8 border-t border-line pt-5 text-xs leading-relaxed text-ink-soft">Access is restricted to authorized staff accounts.</p>
    </section>
  </main>
}

export function StaffLoginPage() {
  const { loginStaff, isAuthenticated, user, loading } = useAuthStore()
  const navigate = useNavigate()
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [error, setError] = useState('')
  if (isAuthenticated && user && ['ADMIN', 'LIBRARIAN'].includes(user.role))
    return <Navigate to={user.role === 'ADMIN' ? '/admin' : '/librarian'} replace />
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const response = await loginStaff(email, password)
      setPassword('')
      navigate(response.user.role === 'ADMIN' ? '/admin' : '/librarian', { replace: true })
    } catch (reason) {
      setPassword('')
      setError(reason instanceof Error ? reason.message : 'Unable to sign in.')
    }
  }
  return <StaffAuthLayout>
    <h1 className="font-display text-3xl text-ink">Authorized library personnel only</h1>
    {error && <p role="alert" className="mt-5 text-sm text-brand">{error}</p>}
    <form onSubmit={submit} className="mt-8 space-y-5">
      <div><label className="auth-label" htmlFor="staff-email">Email</label><input id="staff-email" className="auth-input" type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required disabled={loading} /></div>
      <div><label className="auth-label" htmlFor="staff-password">Password</label><input id="staff-password" className="auth-input" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required disabled={loading} /></div>
      <button type="submit" className="auth-btn" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
    </form>
  </StaffAuthLayout>
}
