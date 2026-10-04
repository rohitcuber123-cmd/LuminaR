import { useRef, useState } from 'react'
import { RotateCw, Info } from 'lucide-react'
import { renewLoan, type RenewalLoan, type RenewalResult } from '../lib/loanRenewal'

export function LoanRenewalControl({ loan, onRenewed, assisted = false, compact = false, className = '' }: {
  loan: RenewalLoan
  onRenewed: (result: RenewalResult) => void | Promise<void>
  assisted?: boolean
  compact?: boolean
  className?: string
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pending = useRef(false)
  const attempt = useRef({ due: '', id: '' })
  const settings = loan.renewal

  if (!settings) return null

  async function renew() {
    if (pending.current || !settings?.eligible) return
    pending.current = true
    setBusy(true)
    setError('')
    if (attempt.current.due !== loan.due_date) attempt.current = { due: loan.due_date, id: crypto.randomUUID() }
    try {
      await onRenewed(await renewLoan(loan, attempt.current.id, assisted))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to renew this loan.')
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  const isLimitReached = settings.reason === 'RENEWAL_LIMIT_REACHED'
  const showMessage = !settings.eligible && settings.message && !(compact && isLimitReached)

  return (
    <div className={`loan-renewal-control flex flex-col items-start gap-1.5 ${className}`}>
      <div className="renewal-widget inline-flex items-stretch rounded-sm border border-line bg-paper shadow-2xs overflow-hidden transition-all duration-150">
        <button
          type="button"
          title={!settings.eligible ? settings.message || undefined : undefined}
          disabled={busy || !settings.eligible}
          onClick={() => void renew()}
          className={`renewal-button font-display inline-flex items-center gap-1.5 px-3 py-2 text-[0.68rem] tracking-wider uppercase transition-colors select-none ${
            settings.eligible
              ? 'bg-paper text-brand hover:bg-brand hover:text-paper cursor-pointer active:bg-brand-dark'
              : 'bg-panel/40 text-ink-soft/40 cursor-not-allowed'
          } ${compact ? 'py-1 px-2 text-[0.65rem]' : ''}`}
        >
          <RotateCw className={`h-3 w-3 shrink-0 ${busy ? 'animate-spin' : ''}`} aria-hidden="true" />
          <span>{busy ? 'Renewing…' : 'Renew'}</span>
        </button>
        <span
          className={`renewal-counter inline-flex items-center border-l border-line bg-panel/60 px-2.5 py-2 text-[0.65rem] font-medium text-ink-soft whitespace-nowrap select-none ${
            compact ? 'py-1 px-2 text-[0.62rem]' : ''
          }`}
        >
          Renewals: {settings.renewal_count} / {settings.max_renewals}
        </span>
      </div>

      {showMessage && (
        <small className="flex items-center gap-1 text-[0.65rem] text-ink-soft/75 max-w-[220px] leading-tight">
          <Info className="h-3 w-3 shrink-0 text-ink-soft/50" aria-hidden="true" />
          <span>{settings.message}</span>
        </small>
      )}

      {error && (
        <p role="alert" className="text-[0.68rem] text-brand font-medium leading-tight max-w-[220px]">
          {error}
        </p>
      )}
    </div>
  )
}

