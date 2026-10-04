import { Link } from 'react-router-dom'
import { Library, ArrowLeft } from 'lucide-react'

export function LibrarianPlaceholder() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 py-20">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand/10">
        <Library className="h-8 w-8 text-brand" />
      </div>

      <h1 className="mt-6 font-display text-[clamp(1.6rem,3.5vw,2.2rem)] text-ink">
        Librarian Dashboard
      </h1>

      <p className="mt-3 max-w-[24rem] text-center text-sm leading-relaxed text-ink-soft">
        The librarian dashboard is being prepared. You'll be able to manage
        inventory, process issues and returns, and handle reservations here.
      </p>

      <Link
        to="/"
        className="mt-8 inline-flex items-center gap-2 font-display text-[0.78rem] tracking-wide text-brand transition-colors hover:text-brand-dark"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Library
      </Link>
    </div>
  )
}
