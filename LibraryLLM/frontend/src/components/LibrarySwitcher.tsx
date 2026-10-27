import { LuminarSelect } from './LuminarSelect'
import { useNavigate } from 'react-router-dom'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { useAuthStore } from '../store/useAuthStore'
import { isLibraryStaff, libraryRole, libraryWorkspaceHome } from '../lib/libraryWorkspace'

/** Switch to the global catalogue or another library in the same membership mode. */
export function LibrarySwitcher({ staff = false, compact = false, global = false }: { staff?: boolean; compact?: boolean; global?: boolean }) {
  const state = useInstitutionStore(), navigate = useNavigate()
  const token = useAuthStore(s => s.token)
  const libraries = state.libraries.filter(l => global ? !!token && state.session === token && !!libraryRole(l) : staff ? isLibraryStaff(l) : libraryRole(l) === 'GENERAL_USER')
  const selected = global ? 'global' : staff ? state.staffLibraryId : state.patronLibraryId
  return <label className="workspace-switcher">{!compact && (global ? 'Catalogue' : staff ? 'Staff library' : 'Patron library')}<LuminarSelect searchable={libraries.length > 8} aria-label={global ? 'Switch catalogue' : staff ? 'Switch staff library' : 'Switch patron library'} value={selected || ''} disabled={state.loading} onChange={e => { if (e.target.value === 'global') { navigate('/'); return } const row = libraries.find(l => l.library_id === e.target.value); if (row) navigate(libraryWorkspaceHome(row)) }}>
    {!selected && <option value="">Choose a library</option>}<option value="global">Global catalogue</option>{libraries.map(l => <option key={l.library_id} value={l.library_id}>{l.name}</option>)}
  </LuminarSelect></label>
}
