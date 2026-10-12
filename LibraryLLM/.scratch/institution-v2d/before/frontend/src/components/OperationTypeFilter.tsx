import { useEffect, useId, useRef, useState } from 'react'

export function OperationTypeFilter({ value, types, onChange }: {
  value: string; types: string[]; onChange: (value: string) => void
}) {
  const id = useId(), root = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false), [active, setActive] = useState(0)
  const choices = ['', ...types]
  const label = (key: string) => key ? key.toLowerCase().replaceAll('_', ' ').replace(/^./, c => c.toUpperCase()) : 'All operations'
  function choose(index: number) { onChange(choices[index]); setOpen(false) }
  useEffect(() => {
    if (!open) return
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [open])
  return <div className="admin-operation-filter" ref={root} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
  }}>
    <button type="button" role="combobox" aria-label="Operation type" aria-expanded={open} aria-haspopup="listbox"
      aria-controls={`${id}-list`} aria-activedescendant={open ? `${id}-${active}` : undefined}
      onClick={() => { setActive(Math.max(0, choices.indexOf(value))); setOpen(v => !v) }}
      onKeyDown={event => {
        if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
          event.preventDefault()
          const current = open ? active : Math.max(0, choices.indexOf(value))
          setActive(event.key === 'Home' ? 0 : event.key === 'End' ? choices.length - 1 : Math.max(0, Math.min(choices.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1))))
          setOpen(true)
        } else if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          if (open) choose(active); else { setActive(Math.max(0, choices.indexOf(value))); setOpen(true) }
        } else if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
        else if (event.key === 'Tab') setOpen(false)
      }}>{label(value)}<span aria-hidden="true" className={open ? 'is-open' : ''}>⌄</span></button>
    {open && <div id={`${id}-list`} role="listbox" aria-label="Operation types">{choices.map((key, index) => <button
      key={key} type="button" role="option" id={`${id}-${index}`} aria-selected={value === key} tabIndex={-1}
      className={active === index ? 'is-active' : ''} onPointerMove={() => setActive(index)}
      onMouseDown={event => event.preventDefault()} onClick={() => choose(index)}>{label(key)}{value === key && <span aria-hidden="true">✓</span>}</button>)}</div>}
  </div>
}
