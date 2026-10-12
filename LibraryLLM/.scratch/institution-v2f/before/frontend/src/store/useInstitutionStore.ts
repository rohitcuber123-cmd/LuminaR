import { create } from 'zustand'
import { institutionApi, type Library, type Page } from '../lib/institutions'
import { isLibraryStaff, libraryRole, patronPath, type LibraryWorkspace } from '../lib/libraryWorkspace'

const storageKey = 'luminar_workspace_contexts'
let requestSequence = 0, refreshSequence = 0
const selections = { PATRON: 0, STAFF: 0 }
type State = {
  owner: string | null; session: string | null; libraries: Library[]
  patronLibraryId: string | null; staffLibraryId: string | null; workspace: LibraryWorkspace | null
  /** Route-local compatibility projection for existing tenant views, never the global patron selection. */
  activeId: string | null; loading: boolean; error: string | null
  syncSession: (owner: string | null, session: string | null) => void
  reset: () => void; refresh: () => Promise<void>
  select: (libraryId: string) => Promise<Library | null>
}
const emptyContexts = { activeId: null, patronLibraryId: null, staffLibraryId: null, workspace: null }
function persist(state: State) {
  if (state.owner && state.session) localStorage.setItem(storageKey, JSON.stringify({ owner: state.owner, patronLibraryId: state.patronLibraryId, staffLibraryId: state.staffLibraryId }))
  else localStorage.removeItem(storageKey)
}
function validId(value: unknown): string | null { return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value) ? value : null }

export const useInstitutionStore = create<State>((set, get) => ({
  owner: null, session: null, libraries: [], ...emptyContexts, loading: false, error: null,
  reset: () => {
    requestSequence++; refreshSequence++; selections.PATRON++; selections.STAFF++
    localStorage.removeItem(storageKey); localStorage.removeItem('luminar_active_library')
    set({ owner: null, session: null, libraries: [], ...emptyContexts, loading: false, error: null })
  },
  syncSession: (owner, session) => {
    if (owner === get().owner && session === get().session) return
    requestSequence++; refreshSequence++; selections.PATRON++; selections.STAFF++
    let patronLibraryId = null, staffLibraryId = null
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || 'null')
      if (owner && session && saved?.owner === owner) { patronLibraryId = validId(saved.patronLibraryId); staffLibraryId = validId(saved.staffLibraryId) }
    } catch { /* Malformed convenience state grants no authority. */ }
    localStorage.removeItem(storageKey); localStorage.removeItem('luminar_active_library')
    set({ owner, session, libraries: [], ...emptyContexts, patronLibraryId, staffLibraryId, loading: !!session, error: null })
    if (owner && session) void get().refresh()
  },
  refresh: async () => {
    const { owner, session } = get(), refresh = ++refreshSequence
    if (!owner || !session) return
    set({ loading: true, error: null })
    try {
      const libraries: Library[] = []
      for (let offset = 0; ; offset += 100) {
        const page = await institutionApi<Page<Library>>(`/me/libraries?offset=${offset}&limit=100`)
        if (get().session !== session || get().owner !== owner || refresh !== refreshSequence) return
        libraries.push(...page.results)
        if (!page.has_more) break
      }
      const patronLibraryId = libraries.some(l => l.library_id === get().patronLibraryId && libraryRole(l) === 'GENERAL_USER') ? get().patronLibraryId : null
      const staffLibraryId = libraries.some(l => l.library_id === get().staffLibraryId && isLibraryStaff(l)) ? get().staffLibraryId : null
      const activeId = libraries.some(l => l.library_id === get().activeId && libraryRole(l)) ? get().activeId : null
      set({ libraries, patronLibraryId, staffLibraryId, activeId, loading: false })
      persist(get())
    } catch (error) {
      if (get().session === session && get().owner === owner && refresh === refreshSequence) {
        localStorage.removeItem(storageKey)
        set({ libraries: [], ...emptyContexts, loading: false, error: error instanceof Error ? error.message : 'Unable to load libraries.' })
      }
    }
  },
  select: async libraryId => {
    const request = ++requestSequence, { owner, session } = get()
    const known = get().libraries.find(l => l.library_id === libraryId)
    const expectedMode = isLibraryStaff(known) ? 'STAFF' : 'PATRON'
    const selection = ++selections[expectedMode]
    const context = await institutionApi<{ library: Library; membership: NonNullable<Library['membership']> }>(`/libraries/${encodeURIComponent(libraryId)}/context`)
    if (selection !== selections[expectedMode] || get().owner !== owner || get().session !== session || !session) return null
    const updated = { ...context.library, membership: context.membership }
    const role = libraryRole(updated)
    if (!role) throw new Error('Active membership is required to open this library.')
    const workspace: LibraryWorkspace = isLibraryStaff(updated) ? 'STAFF' : 'PATRON'
    set({ libraries: [...get().libraries.filter(l => l.library_id !== libraryId), updated], error: null,
      ...(workspace === 'STAFF' ? { staffLibraryId: libraryId, ...(get().patronLibraryId === libraryId ? { patronLibraryId: null } : {}) } : { patronLibraryId: libraryId, ...(get().staffLibraryId === libraryId ? { staffLibraryId: null } : {}) }),
      ...(request === requestSequence ? { activeId: libraryId, workspace } : {}) })
    persist(get()); return request === requestSequence ? updated : null
  },
}))

export function activeLibrary(state: Pick<State, 'libraries' | 'activeId'>) { return state.libraries.find(l => l.library_id === state.activeId) ?? null }
export function patronLibrary(state: Pick<State, 'libraries' | 'patronLibraryId'>) { return state.libraries.find(l => l.library_id === state.patronLibraryId && libraryRole(l) === 'GENERAL_USER') ?? null }
export function staffLibrary(state: Pick<State, 'libraries' | 'staffLibraryId'>) { return state.libraries.find(l => l.library_id === state.staffLibraryId && isLibraryStaff(l)) ?? null }

export function patronCatalogueDestination() { const selected = patronLibrary(useInstitutionStore.getState()); return selected ? patronPath(selected.library_id, 'catalogue') : '/account/libraries?group=patron' }
