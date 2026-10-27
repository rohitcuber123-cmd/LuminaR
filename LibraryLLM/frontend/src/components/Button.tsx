import type { ComponentProps } from 'react'

export type ButtonProps = ComponentProps<'button'> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; busy?: boolean }
export function Button({ variant = 'primary', busy = false, disabled, className = '', type = 'button', ...props }: ButtonProps) {
  return <button {...props} type={type} disabled={disabled || busy} aria-busy={busy || undefined}
    className={`ui-button${variant === 'primary' ? '' : ` ui-${variant}`} ${className}`} />
}
export function IconButton({ className = '', ...props }: ComponentProps<'button'> & { 'aria-label': string }) {
  return <button {...props} type={props.type || 'button'} className={`ui-icon-button ${className}`} />
}
