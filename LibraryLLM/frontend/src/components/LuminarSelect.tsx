import { Children, isValidElement, useEffect, useId, useRef, useState, type ReactNode, type SelectHTMLAttributes } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronDown } from 'lucide-react'

type Option = { value: string; label: string; disabled: boolean }
type Props = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'multiple' | 'size'> & { searchable?: boolean }
function optionsFrom(children: ReactNode): Option[] {
  return Children.toArray(children).flatMap(child => {
    if (!isValidElement<{ value?: string; children?: ReactNode; disabled?: boolean }>(child)) return []
    if (child.type !== 'option') return optionsFrom(child.props.children)
    const label = Children.toArray(child.props.children).join('')
    return [{ value: String(child.props.value ?? label), label, disabled: !!child.props.disabled }]
  })
}

/** One visible combobox. The hidden native select preserves FormData/reset/validation semantics. */
export function LuminarSelect({ children, value, defaultValue, onChange, searchable = false, id, className = '', style, ...props }: Props) {
  const uid = useId(), triggerId = id || `luminar-select-${uid}`, listId = `${triggerId}-options`
  const options = optionsFrom(children)
  const [internal, setInternal] = useState(String(defaultValue ?? options[0]?.value ?? ''))
  const selected = String(value ?? internal)
  const [open, setOpen] = useState(false), [query, setQuery] = useState(''), [active, setActive] = useState(selected), [invalid, setInvalid] = useState(false)
  const [portal, setPortal] = useState<HTMLElement | null>(null)
  const trigger = useRef<HTMLButtonElement>(null), native = useRef<HTMLSelectElement>(null), menu = useRef<HTMLDivElement>(null), search = useRef<HTMLInputElement>(null)
  const typeahead = useRef({ text: '', at: 0 })
  const filtered = options.filter(option => !query || option.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
  const available = filtered.filter(option => !option.disabled)
  const activeId = open && filtered.some(o => o.value === active) ? `${listId}-${options.findIndex(o => o.value === active)}` : undefined
  const close = (restore = false) => { setOpen(false); setQuery(''); if (restore) trigger.current?.focus() }
  const show = () => { if (!props.disabled) { setPortal(trigger.current?.closest('dialog') || document.body); setQuery(''); setActive(options.find(o => o.value === selected && !o.disabled)?.value ?? options.find(o => !o.disabled)?.value ?? ''); setOpen(true) } }
  function choose(option?: Option) {
    if (!option || option.disabled || !native.current) return
    native.current.value = option.value
    const FormEvent = native.current.ownerDocument.defaultView!.Event
    native.current.dispatchEvent(new FormEvent('change', { bubbles: true }))
    close(true)
  }
  function keyDown(event: React.KeyboardEvent) {
    if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); close(true); return }
    if (event.key === 'Tab') { close(); return }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault()
      if (!open) { show(); return }
      const current = available.findIndex(o => o.value === active)
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? available.length - 1 : Math.max(0, Math.min(available.length - 1, current + (event.key === 'ArrowDown' ? 1 : -1)))
      if (available[index]) setActive(available[index].value)
      return
    }
    if (event.key === 'Enter' || event.key === ' ' && event.target !== search.current) {
      event.preventDefault(); if (open) choose(available.find(o => o.value === active)); else show(); return
    }
    if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && event.target !== search.current) {
      event.preventDefault()
      const now = event.timeStamp, prior = typeahead.current
      const text = (now - prior.at < 700 ? prior.text : '') + event.key.toLocaleLowerCase()
      typeahead.current = { text, at: now }
      const match = options.find(o => !o.disabled && o.label.toLocaleLowerCase().startsWith(text))
      if (match) { if (open) setActive(match.value); else choose(match) }
    }
  }
  useEffect(() => {
    if (!open || props.disabled) return
    const popup = menu.current, button = trigger.current
    if (!popup || !button) return
    function position() {
      if (!popup || !button) return
      const bounds = button.getBoundingClientRect(), gap = 6, margin = 8
      const width = Math.min(Math.max(bounds.width, 160), window.innerWidth - margin * 2)
      const below = window.innerHeight - bounds.bottom - margin - gap, above = bounds.top - margin - gap
      const down = below >= Math.min(250, popup.scrollHeight) || below >= above
      popup.style.width = `${width}px`
      popup.style.left = `${Math.max(margin, Math.min(bounds.left, window.innerWidth - width - margin))}px`
      popup.style.maxHeight = `${Math.max(80, Math.min(320, down ? below : above))}px`
      popup.style.top = down ? `${bounds.bottom + gap}px` : 'auto'
      popup.style.bottom = down ? 'auto' : `${window.innerHeight - bounds.top + gap}px`
    }
    if (popup.showPopover) popup.showPopover()
    else popup.style.display = 'block'
    position()
    if (searchable) search.current?.focus()
    const outside = (e: PointerEvent) => { if (!popup.contains(e.target as Node) && !button.contains(e.target as Node)) { setOpen(false); setQuery('') } }
    const reposition = () => position()
    document.addEventListener('pointerdown', outside)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, true)
    return () => { popup.hidePopover?.(); document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', reposition); window.removeEventListener('scroll', reposition, true) }
  }, [open, props.disabled, searchable])
  useEffect(() => {
    if (open) menu.current?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView?.({ block: 'nearest' })
  }, [active, open])
  useEffect(() => {
    const form = native.current?.form
    const reset = () => { setInternal(String(defaultValue ?? optionsFrom(children)[0]?.value ?? '')); setInvalid(false); setOpen(false) }
    form?.addEventListener('reset', reset)
    return () => form?.removeEventListener('reset', reset)
  }, [defaultValue, children])
  return <span className={`luminar-select ${className}`} style={style}>
    <button ref={trigger} id={triggerId} type="button" role="combobox" className="luminar-select-trigger"
      disabled={props.disabled} aria-label={props['aria-label']} aria-labelledby={props['aria-labelledby']}
      aria-describedby={props['aria-describedby']} aria-invalid={props['aria-invalid'] || invalid || undefined} aria-required={props.required || undefined}
      aria-haspopup="listbox" aria-expanded={open && !props.disabled} aria-controls={open ? listId : undefined}
      aria-activedescendant={activeId}
      onClick={() => open ? close() : show()} onKeyDown={keyDown}>
      <span>{options.find(o => o.value === selected)?.label || 'Choose an option'}</span><ChevronDown size={16} aria-hidden="true" />
    </button>
    <select {...props} ref={native} hidden aria-hidden="true" aria-label={undefined} aria-labelledby={undefined} tabIndex={-1} id={`${triggerId}-native`} value={value === undefined ? internal : value}
      onInvalid={e => { e.preventDefault(); setInvalid(true); trigger.current?.focus() }}
      onChange={event => { setInternal(event.target.value); setInvalid(false); onChange?.(event) }}>{children}</select>
    {open && !props.disabled && portal && createPortal(<div ref={menu} className="luminar-select-menu" popover="manual" onKeyDown={keyDown}>
      {searchable && <input ref={search} type="search" className="luminar-select-search" aria-label="Find an option" aria-controls={listId} aria-activedescendant={activeId} aria-autocomplete="list" placeholder="Type to find…" value={query}
        onChange={e => { setQuery(e.target.value); const next = options.find(o => !o.disabled && o.label.toLocaleLowerCase().includes(e.target.value.toLocaleLowerCase())); setActive(next?.value ?? '') }} />}
      <div id={listId} role="listbox" aria-labelledby={triggerId} className="luminar-select-options">
        {filtered.map(option => <div key={option.value} id={`${listId}-${options.indexOf(option)}`} role="option" aria-selected={option.value === selected}
          aria-disabled={option.disabled || undefined} data-active={option.value === active} className="luminar-select-option"
          onPointerMove={() => { if (!option.disabled) setActive(option.value) }} onMouseDown={e => e.preventDefault()} onClick={() => choose(option)}>
          <span>{option.label}</span>{option.value === selected && <Check size={16} aria-hidden="true" />}
        </div>)}
        {!filtered.length && <p role="status" className="luminar-select-empty">No matching options</p>}
      </div>
    </div>, portal)}
  </span>
}
