import { create } from 'zustand'
import {
  getReadingList,
  addToReadingList,
  removeFromReadingList,
  getMyIssues,
  getMyReservations,
} from '../lib/api'

interface LibraryState {
  readingList: string[]
  reservations: any[]
  issues: any[]
  searchQuery: string
  categoryFilter: string
  formatFilter: string

  addToList: (workId: string) => Promise<void>
  removeFromList: (workId: string) => Promise<void>
  toggleList: (workId: string) => Promise<void>
  setSearchQuery: (query: string) => void
  setCategoryFilter: (category: string) => void
  setFormatFilter: (format: string) => void
  isInList: (workId: string) => boolean
  isReserved: (workId: string) => boolean
  fetchUserData: () => Promise<void>
  clearUserData: () => void
}

export const useLibraryStore = create<LibraryState>((set, get) => ({
  readingList: [],
  reservations: [],
  issues: [],
  searchQuery: '',
  categoryFilter: '',
  formatFilter: '',

  fetchUserData: async () => {
    try {
      const [readingListData, issuesData, reservationsData] = await Promise.all<any>([
        getReadingList().catch(() => ({ items: [] })),
        getMyIssues().catch(() => ({ issues: [] })),
        getMyReservations().catch(() => ({ reservations: [] }))
      ])
      
      set({
        readingList: (readingListData.items || []).map((item: any) => item.work_id),
        issues: issuesData.issues || [],
        reservations: reservationsData.reservations || []
      })
    } catch (err) {
      console.error('Failed to fetch user library data:', err)
    }
  },

  clearUserData: () => {
    set({
      readingList: [],
      reservations: [],
      issues: [],
    })
  },

  addToList: async (workId) => {
    try {
      await addToReadingList(workId)
      set((state) => ({
        readingList: state.readingList.includes(workId)
          ? state.readingList
          : [...state.readingList, workId],
      }))
    } catch (err) {
      console.error('Failed to add to reading list', err)
      throw err
    }
  },

  removeFromList: async (workId) => {
    try {
      await removeFromReadingList(workId)
      set((state) => ({
        readingList: state.readingList.filter((id) => id !== workId),
      }))
    } catch (err) {
      console.error('Failed to remove from reading list', err)
      throw err
    }
  },

  toggleList: async (workId) => {
    const { readingList, addToList, removeFromList } = get()
    if (readingList.includes(workId)) {
      await removeFromList(workId)
    } else {
      await addToList(workId)
    }
  },

  setSearchQuery: (query) => set({ searchQuery: query }),
  setCategoryFilter: (category) => set({ categoryFilter: category }),
  setFormatFilter: (format) => set({ formatFilter: format }),

  isInList: (workId) => get().readingList.includes(workId),
  isReserved: (workId) => {
    const { reservations } = get()
    return reservations.some(
      r => r.work_id === workId && (r.status === 'ACTIVE' || r.status === 'READY_FOR_PICKUP')
    )
  },
}))
