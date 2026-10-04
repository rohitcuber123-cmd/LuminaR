import { useState, useEffect, useCallback } from 'react'

interface ToastItem {
  id: number
  message: string
  type: 'success' | 'info' | 'warning'
}

let toastId = 0
const listeners: Set<(toast: ToastItem) => void> = new Set()

export function showToast(message: string, type: 'success' | 'info' | 'warning' = 'success') {
  const toast: ToastItem = { id: ++toastId, message, type }
  listeners.forEach((fn) => fn(toast))
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((toast: ToastItem) => {
    setToasts((prev) => [...prev, toast])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id))
    }, 3000)
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
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`${bgMap[toast.type]} animate-toast-in rounded-lg px-5 py-3 text-sm font-medium shadow-xl`}
        >
          {toast.message}
        </div>
      ))}
    </div>
  )
}
