import type { ReactNode } from 'react'

export function StatusPill({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'online' | 'physical' | 'combined' }) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>
}
