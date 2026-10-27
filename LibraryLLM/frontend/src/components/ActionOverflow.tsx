import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { MoreHorizontal } from 'lucide-react'
import { IconButton } from './Button'

/** Portal placement keeps menus outside clipped carousel rails. Native links retain Tab navigation. */
export function ActionOverflow({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false), [position, setPosition] = useState({ top: 0, left: 0 })
  const trigger = useRef<HTMLButtonElement>(null), menu = useRef<HTMLDivElement>(null), id = useId()
  useLayoutEffect(() => {
    if (!open) return
    function place() {
      const rect = trigger.current?.getBoundingClientRect(), panel = menu.current
      if (!rect || !panel) return
      const width = panel.offsetWidth, height = panel.offsetHeight
      const top = rect.bottom + height + 8 > window.innerHeight ? rect.top - height - 6 : rect.bottom + 6
      setPosition({ left: Math.max(8, Math.min(rect.right - width, window.innerWidth - width - 8)), top: Math.max(8, Math.min(top, window.innerHeight - height - 8)) })
    }
    place()
    menu.current?.querySelector<HTMLElement>('a,button')?.focus({ preventScroll: true })
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true) }
  }, [open])
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus({ preventScroll: true }) }
    }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [open])
  return <>
    <IconButton ref={trigger} className="book-overflow-trigger" aria-label={label} aria-expanded={open} aria-controls={open ? id : undefined}
      onClick={() => setOpen(value => !value)} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true) } }}><MoreHorizontal size={18} aria-hidden="true" /></IconButton>
    {open && createPortal(<div ref={menu} id={id} className="action-overflow-panel" style={position} aria-label={label}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget) && event.relatedTarget !== trigger.current) setOpen(false) }}
      onClick={event => { if ((event.target as Element).closest('a')) setOpen(false) }}>{children}</div>, document.body)}
  </>
}
