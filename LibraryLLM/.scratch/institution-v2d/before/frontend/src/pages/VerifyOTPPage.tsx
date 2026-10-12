import { useState, useRef, useEffect, type KeyboardEvent, type ClipboardEvent, type FormEvent } from 'react'
import { useLocation, useNavigate, Navigate, Link } from 'react-router-dom'
import { ShieldCheck, AlertCircle, RotateCw } from 'lucide-react'
import { AuthLayout } from '@/components/AuthLayout'
import { useAuthStore } from '@/store/useAuthStore'

const OTP_LENGTH = 6

export function VerifyOTPPage() {
  const { verifyOtp, resendOtp, loading, isAuthenticated } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()

  // Get email from navigation state (not URL params)
  const email = (location.state as any)?.email || ''

  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(''))
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [cooldown, setCooldown] = useState(0)
  const [resending, setResending] = useState(false)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Cooldown timer — placed before any conditional returns to satisfy Rules of Hooks
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => setCooldown((c) => c - 1), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  // Redirect if no email was provided
  if (!email) {
    return <Navigate to="/signup" replace />
  }

  function handleChange(index: number, value: string) {
    const digit = value.replace(/\D/g, '').slice(-1)
    const next = [...digits]
    next[index] = digit
    setDigits(next)
    setError('')

    if (digit && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH)
    if (!pasted) return
    const next = [...digits]
    for (let i = 0; i < pasted.length; i++) {
      next[i] = pasted[i]
    }
    setDigits(next)
    const focusIdx = Math.min(pasted.length, OTP_LENGTH - 1)
    inputRefs.current[focusIdx]?.focus()
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    const otp = digits.join('')

    if (otp.length !== OTP_LENGTH) {
      setError('Please enter the full 6-digit code.')
      return
    }

    try {
      await verifyOtp(email, otp)
      // Redirect to login with a success flag
      navigate('/login', {
        replace: true,
        state: { verified: true },
      })
    } catch (err: any) {
      const message = err?.message || ''

      if (message.toLowerCase().includes('expired')) {
        setError('Verification code has expired. Please request a new one.')
      } else if (message.toLowerCase().includes('attempts')) {
        setError('Too many failed attempts. Please request a new code.')
      } else if (message.toLowerCase().includes('invalid') || message.includes('400')) {
        setError('Invalid verification code. Please try again.')
      } else if (message.includes('network') || message.includes('fetch')) {
        setError('Unable to connect to LuminaR. Please try again.')
      } else {
        setError(message || 'Verification failed. Please try again.')
      }
    }
  }

  async function handleResend() {
    if (cooldown > 0 || resending) return
    setError('')
    setSuccess('')
    setResending(true)

    try {
      await resendOtp(email)
      setSuccess('A new verification code has been sent to your email.')
      setCooldown(60)

      // Clear the digit inputs
      setDigits(Array(OTP_LENGTH).fill(''))
      inputRefs.current[0]?.focus()
    } catch (err: any) {
      const message = err?.message || ''

      if (message.toLowerCase().includes('already verified')) {
        setSuccess('Your email is already verified!')
        setTimeout(() => navigate('/login', { replace: true }), 2000)
      } else if (message.toLowerCase().includes('wait')) {
        setError(message)
      } else {
        setError(message || 'Failed to resend verification code.')
      }
    } finally {
      setResending(false)
    }
  }

  return (
    <AuthLayout>
      <div>
        <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/10">
          <ShieldCheck className="h-7 w-7 text-brand" />
        </div>

        <h1 className="font-display text-[clamp(1.6rem,3.5vw,2.2rem)] text-ink">
          Verify Email
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          We sent a 6-digit code to{' '}
          <span className="font-medium text-ink">{email}</span>. Enter it below to verify your
          account.
        </p>

        {error && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-brand/8 px-4 py-3 text-sm text-brand">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mt-6 flex items-start gap-2.5 rounded-lg bg-moss/10 px-4 py-3 text-sm text-moss">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8">
          {/* OTP digit boxes */}
          <div className="flex justify-between gap-2.5">
            {digits.map((digit, i) => (
              <input
                key={i}
                ref={(el) => { inputRefs.current[i] = el }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                onPaste={i === 0 ? handlePaste : undefined}
                className="otp-digit"
                aria-label={`Digit ${i + 1}`}
              />
            ))}
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || digits.join('').length !== OTP_LENGTH}
            className="auth-btn mt-8"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="auth-spinner" />
                Verifying...
              </span>
            ) : (
              'Verify & Continue'
            )}
          </button>
        </form>

        {/* Resend */}
        <div className="mt-6 text-center">
          <button
            onClick={handleResend}
            disabled={cooldown > 0 || resending}
            className="inline-flex items-center gap-1.5 text-sm text-ink-soft transition-colors hover:text-brand disabled:text-ink-soft/40"
          >
            <RotateCw className={`h-3.5 w-3.5 ${cooldown > 0 || resending ? '' : 'transition-transform hover:rotate-180'}`} />
            {resending
              ? 'Sending...'
              : cooldown > 0
                ? `Resend in ${cooldown}s`
                : 'Resend code'}
          </button>
        </div>

        <p className="mt-8 text-center text-sm text-ink-soft">
          Wrong email?{' '}
          <Link to="/signup" className="font-medium text-brand transition-colors hover:text-brand-dark">
            Go back
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
