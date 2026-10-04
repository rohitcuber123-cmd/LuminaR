import { create } from 'zustand'
import {
  getToken,
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
  userDataLoading: boolean
  userDataLoaded: boolean
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

let sessionVersion = 0
let requestVersion = 0

export const useLibraryStore = create<LibraryState>((set, get) => ({
  readingList: [],
  reservations: [],
  issues: [],
  userDataLoading: false,
  userDataLoaded: false,
  searchQuery: '',
  categoryFilter: '',
  formatFilter: '',

  fetchUserData: async () => {
    const sessionToken = getToken()
    const version = sessionVersion
    const request = ++requestVersion
    if (!sessionToken) return
    set({ userDataLoading: true })
    try {
      const [readingListData, issuesData, reservationsData] = await Promise.allSettled([
        getReadingList(),
        getMyIssues() as Promise<{ issues: any[] }>,
        getMyReservations() as Promise<{ reservations: any[] }>
      ])
      
      if (sessionToken !== getToken() || version !== sessionVersion || request !== requestVersion) return
      set({
        ...(readingListData.status === 'fulfilled' ? { readingList: readingListData.value.items.map((item: any) => item.work_id) } : {}),
        ...(issuesData.status === 'fulfilled' ? { issues: issuesData.value.issues } : {}),
        ...(reservationsData.status === 'fulfilled' ? { reservations: reservationsData.value.reservations } : {}),
        userDataLoading: false,
        userDataLoaded: true,
      })
    } catch (err) {
      console.error('Failed to fetch user library data:', err)
      if (sessionToken === getToken() && version === sessionVersion && request === requestVersion) {
        set({ userDataLoading: false, userDataLoaded: true })
      }
    }
  },

  clearUserData: () => {
    sessionVersion += 1
    requestVersion += 1
    set({
      readingList: [],
      reservations: [],
      issues: [],
      userDataLoading: false,
      userDataLoaded: false,
    })
  },

  addToList: async (workId) => {
    const sessionToken = getToken()
    const version = sessionVersion
    try {
      await addToReadingList(workId)
      if (sessionToken !== getToken() || version !== sessionVersion) return
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
    const sessionToken = getToken()
    const version = sessionVersion
    try {
      await removeFromReadingList(workId)
      if (sessionToken !== getToken() || version !== sessionVersion) return
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
