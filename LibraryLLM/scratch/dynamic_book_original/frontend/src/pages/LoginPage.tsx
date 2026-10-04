import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, LogIn, AlertCircle, ShieldCheck } from 'lucide-react'
import { AuthLayout } from '@/components/AuthLayout'
import { useAuthStore } from '@/store/useAuthStore'

export function LoginPage() {
  const { login, loading, isAuthenticated, user } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  // Success message from OTP verification
  const verifiedMessage = (location.state as any)?.verified
    ? 'Your account has been verified. Please sign in.'
    : ''

  // If already logged in, redirect based on role
  if (isAuthenticated && user) {
    const from = (location.state as any)?.from?.pathname
    if (from) return <Navigate to={from} replace />
    if (user.role === 'ADMIN') return <Navigate to="/admin" replace />
    if (user.role === 'LIBRARIAN') return <Navigate to="/librarian" replace />
    return <Navigate to="/" replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address.')
      return
    }

    if (!password) {
      setError('Please enter your password.')
      return
    }

    try {
      const response = await login(email, password)

      // Role-based redirect
      const from = (location.state as any)?.from?.pathname
      const role = response?.user?.role

      if (from) {
        navigate(from, { replace: true })
      } else if (role === 'ADMIN') {
        navigate('/admin', { replace: true })
      } else if (role === 'LIBRARIAN') {
        navigate('/librarian', { replace: true })
      } else {
        navigate('/', { replace: true })
      }
    } catch (err: any) {
      const message = err?.message || ''

      // Handle unverified email — redirect to OTP page
      if (message.toLowerCase().includes('verify your email')) {
        navigate('/verify-otp', { state: { email } })
        return
      }

      // Map technical errors to user-friendly messages
      if (message.includes('401') || message.toLowerCase().includes('invalid')) {
        setError('Invalid email or password.')
      } else if (message.includes('network') || message.includes('fetch')) {
        setError('Unable to connect to LuminaR. Please try again.')
      } else {
        setError(message || 'Login failed. Please try again.')
      }
    }
  }

  return (
    <AuthLayout>
      <div>
        <h1 className="font-display text-[clamp(1.6rem,3.5vw,2.2rem)] text-ink">
          Welcome Back
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          Sign in to access your library account.
        </p>

        {verifiedMessage && !error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-moss/10 px-4 py-3 text-sm text-moss">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{verifiedMessage}</span>
          </div>
        )}

        {error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-brand/8 px-4 py-3 text-sm text-brand">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          {/* Email */}
          <div>
            <label htmlFor="login-email" className="auth-label">
              Email Address
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="auth-input"
            />
          </div>

          {/* Password */}
          <div>
            <div className="flex items-center justify-between">
              <label htmlFor="login-password" className="auth-label">
                Password
              </label>
              <button
                type="button"
                className="mb-2 text-[0.7rem] text-ink-soft/70 transition-colors hover:text-brand"
                tabIndex={-1}
              >
                Forgot password?
              </button>
            </div>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                className="auth-input pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-soft/50 transition-colors hover:text-ink-soft"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="auth-btn mt-2"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="auth-spinner" />
                Signing in...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <LogIn className="h-4 w-4" />
                Sign In
              </span>
            )}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-ink-soft">
          Don't have an account?{' '}
          <Link to="/signup" className="font-medium text-brand transition-colors hover:text-brand-dark">
            Create one
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
