import { create } from 'zustand'
import { coreRequest } from '../lib/api'

type State = { session: string | null; roles: string[]; loading: boolean; error: string;
  syncSession: (session: string | null) => void; refresh: () => Promise<void>; reset: () => void }
let version = 0
export const usePlatformStore = create<State>((set, get) => ({
  session: null, roles: [], loading: false, error: '',
  reset: () => { version++; set({ session: null, roles: [], loading: false, error: '' }) },
  syncSession: session => {
    if (session === get().session) return
    version++; set({ session, roles: [], loading: !!session, error: '' })
    if (session) void get().refresh()
  },
  refresh: async () => {
    const session = get().session, request = ++version
    if (!session) return
    set({ loading: true, roles: [], error: '' })
    try {
      const result = await coreRequest<{ roles: string[] }>('/me/platform-access')
      if (!Array.isArray(result.roles) || result.roles.some(role => typeof role !== 'string')) throw new Error('Invalid platform permission response.')
      if (get().session === session && request === version) set({ roles: result.roles, loading: false })
    } catch (reason) {
      if (get().session === session && request === version) set({ roles: [], loading: false, error: reason instanceof Error ? reason.message : 'Unable to check platform access.' })
    }
  },
}))
export function platformAdmin(state: Pick<State, 'roles' | 'session'>, token: string | null) {
  return !!token && state.session === token && state.roles.includes('PLATFORM_ADMIN')
}
