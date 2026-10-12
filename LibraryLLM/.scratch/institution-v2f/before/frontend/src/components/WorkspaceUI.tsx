import { menuKeys } from '../lib/menuKeyboard'
import { useState, type ReactNode } from 'react'
import { MoreHorizontal } from 'lucide-react'
import { Modal } from './StaffUI'

export function PageHeading({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <div className="ui-page-heading"><div>{eyebrow && <p className="ui-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="ui-description">{description}</p>}</div>{actions && <div className="ui-actions">{actions}</div>}</div>
}
export function StatePanel({ title, children, kind = 'empty', action }: { title: string; children?: ReactNode; kind?: 'empty' | 'error' | 'loading'; action?: ReactNode }) {
  return <div className={`ui-state ui-state-${kind}`} role={kind === 'error' ? 'alert' : kind === 'loading' ? 'status' : undefined}><strong>{title}</strong>{children && <p>{children}</p>}{action && <div className="ui-actions">{action}</div>}</div>
}
export function ActionMenu({ label, actions }: { label: string; actions: { label: string; run: () => void; danger?: boolean; disabled?: boolean }[] }) {
  const [open, setOpen] = useState(false)
  return <><button className="ui-icon-button secondary" aria-label={`Actions for ${label}`} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(true)}><MoreHorizontal size={18} /></button>{open && <Modal className="ui-action-menu" title={`Actions · ${label}`} onClose={() => setOpen(false)}><div role="menu" aria-label={`Actions for ${label}`} onKeyDown={menuKeys}>{actions.map((item, index) => <button key={item.label} role="menuitem" data-autofocus={index === 0 || undefined} disabled={item.disabled} className={item.danger ? 'ui-danger' : 'secondary'} onClick={() => { setOpen(false); item.run() }}>{item.label}</button>)}</div></Modal>}</>
}
