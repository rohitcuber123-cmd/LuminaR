export type ReadNowState = 'HIDDEN' | 'LOGIN' | 'LOADING' | 'DIRECT' | 'AUTO_BORROW'

interface ReadNowPolicyInput {
  authenticated: boolean
  role?: string
  readable: boolean
  borrowed: boolean
  accessReady: boolean
  borrowAction: string
}

export function readNowState(input: ReadNowPolicyInput): ReadNowState {
  if (!input.readable) return 'HIDDEN'
  if (!input.authenticated) return 'LOGIN'
  if (input.borrowed) return 'DIRECT'
  if (input.role !== 'GENERAL_USER') return 'HIDDEN'
  if (!input.accessReady) return 'LOADING'
  return input.borrowAction === 'BORROW' ? 'AUTO_BORROW' : 'HIDDEN'
}

interface ReadNowOperation {
  workId: string
  borrowed: boolean
  borrow: (workId: string) => Promise<unknown>
  refresh: () => Promise<unknown>
  navigate: (path: string) => void
}

export function createReadNowOperation() {
  let inFlight = false

  return async (operation: ReadNowOperation): Promise<boolean> => {
    if (inFlight) return false
    inFlight = true
    try {
      if (!operation.borrowed) {
        await operation.borrow(operation.workId)
        await operation.refresh()
      }
      operation.navigate(`/book/${encodeURIComponent(operation.workId)}/read`)
      return true
    } finally {
      inFlight = false
    }
  }
}
