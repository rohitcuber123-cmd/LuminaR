import { useAuthStore } from '../store/useAuthStore'
import { useLibraryStore } from '../store/useLibraryStore'
import type { BackendBook } from '../lib/api'

export type ActionState = 'BORROW' | 'RESERVE' | 'BORROWED' | 'RESERVED' | 'SIGN_IN'

export function useBookActionState(book: BackendBook | null) {
  const { isAuthenticated } = useAuthStore()
  const { issues, reservations } = useLibraryStore()

  // Handle null book during loading phase
  if (!book) {
    return { action: 'SIGN_IN' as ActionState, adjustedAvailable: 0 }
  }

  if (!isAuthenticated) {
    return { action: 'SIGN_IN' as ActionState, adjustedAvailable: Math.max(0, Number(book.available_copies ?? 0)) }
  }

  const workId = book.work_id

  // Check if user already borrowed this specific work
  const isAlreadyBorrowed = issues.some(
    i => i.work_id === workId && i.status === 'ISSUED'
  )

  if (isAlreadyBorrowed) {
    return { action: 'BORROWED' as ActionState, adjustedAvailable: Math.max(0, Number(book.available_copies ?? 0)) }
  }

  // Check if user already reserved this specific work
  const isAlreadyReserved = reservations.some(
    r => r.work_id === workId && (r.status === 'ACTIVE' || r.status === 'READY_FOR_PICKUP')
  )

  if (isAlreadyReserved) {
    return { action: 'RESERVED' as ActionState, adjustedAvailable: Math.max(0, Number(book.available_copies ?? 0)) }
  }

  // Available copies from backend
  const availableCopies = Math.max(0, Number(book.available_copies ?? 0))

  if (availableCopies > 0) {
    return { action: 'BORROW' as ActionState, adjustedAvailable: availableCopies }
  }

  return { action: 'RESERVE' as ActionState, adjustedAvailable: 0 }
}
