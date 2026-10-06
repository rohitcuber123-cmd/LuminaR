import { create } from 'zustand'
export const useEventStore = create<{ scope: string; count: number; revision: number; set: (scope: string, count: number) => void }>(set => ({ scope: '', count: 0, revision: 0, set: (scope, count) => set(state => ({ scope, count, revision: state.revision + 1 })) }))
