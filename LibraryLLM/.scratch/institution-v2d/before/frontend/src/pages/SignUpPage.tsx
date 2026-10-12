import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, UserPlus, AlertCircle } from 'lucide-react'
import { AuthLayout } from '@/components/AuthLayout'
import { useAuthStore } from '@/store/useAuthStore'

export function SignUpPage() {
  const { register, loading, isAuthenticated } = useAuthStore()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')

    if (!name.trim()) {
      setError('Please enter your name.')
      return
    }

    if (!email.trim()) {
      setError('Please enter your email address.')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address.')
      return
    }

    if (!password) {
      setError('Please enter a password.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    try {
      // Send only name, email, password — no role field.
      // Backend hardcodes GENERAL_USER.
      await register({ name: name.trim(), email, password })
      navigate('/verify-otp', { state: { email } })
    } catch (err: any) {
      const message = err?.message || ''

      if (message.includes('409') || message.toLowerCase().includes('already registered')) {
        setError('An account with this email already exists.')
      } else if (message.includes('422') || message.toLowerCase().includes('check')) {
        setError('Please check the information you entered.')
      } else if (message.includes('network') || message.includes('fetch')) {
        setError('Unable to connect to LuminaR. Please try again.')
      } else {
        setError(message || 'Registration failed. Please try again.')
      }
    }
  }

  return (
    <AuthLayout>
      <div>
        <h1 className="font-display text-[clamp(1.6rem,3.5vw,2.2rem)] text-ink">
          Create Account
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          Join LuminaR and start exploring our collection.
        </p>

        {error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-brand/8 px-4 py-3 text-sm text-brand">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="signup-name" className="auth-label">
              Full Name
            </label>
            <input
              id="signup-name"
              type="text"
              autoComplete="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your full name"
              className="auth-input"
            />
          </div>

          {/* Email */}
          <div>
            <label htmlFor="signup-email" className="auth-label">
              Email Address
            </label>
            <input
              id="signup-email"
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
            <label htmlFor="signup-password" className="auth-label">
              Password
            </label>
            <div className="relative">
              <input
                id="signup-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
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

          {/* Confirm Password */}
          <div>
            <label htmlFor="signup-confirm" className="auth-label">
              Confirm Password
            </label>
            <input
              id="signup-confirm"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-enter your password"
              className="auth-input"
            />
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
                Creating account...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                <UserPlus className="h-4 w-4" />
                Create Account
              </span>
            )}
          </button>
        </form>

        <p className="mt-8 text-center text-sm text-ink-soft">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand transition-colors hover:text-brand-dark">
            Sign in
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
