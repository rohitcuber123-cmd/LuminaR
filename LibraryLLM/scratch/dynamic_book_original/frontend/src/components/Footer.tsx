import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, BookOpen } from 'lucide-react'

const COLUMNS: { heading: string; links: { label: string; to: string }[] }[] = [
  {
    heading: 'Explore',
    links: [
      { label: 'Full Catalog', to: '/catalog' },
      { label: 'New Arrivals', to: '/#new-arrivals' },
      { label: 'Categories', to: '/catalog' },
      { label: "Librarian's Picks", to: '/' },
    ],
  },
  {
    heading: 'Services',
    links: [
      { label: 'Get a Library Card', to: '/' },
      { label: 'Interlibrary Loan', to: '/' },
      { label: 'Study Rooms', to: '/' },
      { label: 'Events & Programs', to: '/' },
    ],
  },
  {
    heading: 'Help',
    links: [
      { label: 'Renew or Return', to: '/' },
      { label: 'Fines & Fees', to: '/' },
      { label: 'Accessibility', to: '/' },
      { label: 'Contact Us', to: '/' },
    ],
  },
]

function Newsletter() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email) return
    setSubmitted(true)
  }

  return (
    <div className="border-b border-paper/10 px-6 py-16 md:px-10">
      <div className="mx-auto max-w-[90rem]">
        <h2 className="font-display text-[clamp(1.8rem,4.4vw,2.8rem)] text-paper">Be the First to Know</h2>
        <p className="mt-3 max-w-[26rem] text-sm text-paper/55">
          New arrivals, holds ready for pickup, and library events — straight to your inbox, nothing else.
        </p>

        <form onSubmit={handleSubmit} className="mt-7 flex max-w-[24rem] items-center border-b border-paper/40 pb-2">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter your email"
            className="w-full bg-transparent text-sm text-paper placeholder:text-paper/40 focus:outline-none"
          />
          <button
            type="submit"
            aria-label="Subscribe"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand text-paper transition-transform hover:scale-105"
          >
            <ArrowUpRight className="h-4 w-4" />
          </button>
        </form>
        {submitted && <p className="mt-3 text-xs text-brand">You're on the list — welcome to LuminaR.</p>}
      </div>
    </div>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-line bg-ink text-paper/80">
      <Newsletter />

      <div className="mx-auto max-w-[90rem] px-6 py-16 md:px-10">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2">
            <Link to="/" className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-brand" strokeWidth={1.75} />
              <span className="font-display text-[1.1rem] text-paper">
                Lumina<span className="text-brand">R</span>
              </span>
            </Link>
            <p className="mt-4 max-w-[22rem] text-sm leading-relaxed text-paper/55">
              A public library catalog for readers who want more than a card list — browse by category,
              track holds, and find your next book faster.
            </p>
            <p className="mt-6 text-sm text-paper/55">
              228 Elm Street, Rivergate
              <br />
              Mon&ndash;Sat, 9am&ndash;8pm
            </p>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.heading}>
              <h3 className="font-display mb-4 text-[0.7rem] tracking-[0.2em] text-paper/50">{col.heading}</h3>
              <ul className="space-y-2.5">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link to={link.to} className="text-sm text-paper/70 transition-colors hover:text-brand">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-paper/10 pt-8 text-xs text-paper/45 sm:flex-row">
          <p>&copy; {new Date().getFullYear()} LuminaR Public Library. All rights reserved.</p>
          <p>Books shown are illustrative catalog entries.</p>
        </div>
      </div>
    </footer>
  )
}
