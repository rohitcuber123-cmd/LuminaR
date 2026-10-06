import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'

interface ToastOptions { title?: string; href?: string; actionLabel?: string; durationMs?: number; scope?: string }

interface ToastItem extends ToastOptions {
  id: number
  message: string
  type: 'success' | 'info' | 'warning'
}

let toastId = 0
const listeners: Set<(toast: ToastItem) => void> = new Set()

export function showToast(message: string, type: 'success' | 'info' | 'warning' = 'success', options: ToastOptions = {}) {
  const toast: ToastItem = { id: ++toastId, message, type, ...options }
  listeners.forEach((fn) => fn(toast))
}

export function ToastContainer() {
  const token = useAuthStore(s => s.token)
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((toast: ToastItem) => {
    setToasts((prev) => [...prev, toast])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id))
    }, toast.durationMs ?? 3000)
  }, [])

  useEffect(() => {
    listeners.add(addToast)
    return () => { listeners.delete(addToast) }
  }, [addToast])

  const bgMap = {
    success: 'bg-moss text-paper',
    info: 'bg-ink text-paper',
    warning: 'bg-brand text-paper',
  }

  return (
    <div className="fixed bottom-24 right-6 z-[9999] flex flex-col gap-2">
      {toasts.filter(toast => !toast.scope || toast.scope === token).map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={`${bgMap[toast.type]} animate-toast-in max-w-[min(24rem,calc(100vw-3rem))] rounded-lg px-5 py-3 text-sm font-medium shadow-xl`}
        >
          {toast.title && <strong className="mb-1 block font-display">{toast.title}</strong>}
          <p>{toast.message}</p>
          {toast.href && <Link className="mt-2 inline-block underline underline-offset-4" to={toast.href}>{toast.actionLabel || 'View'}</Link>}
        </div>
      ))}
    </div>
  )
}
