import { useNavigate } from 'react-router-dom'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryRole, libraryWorkspaceHome } from '../lib/libraryWorkspace'

/** A workspace-local switcher never lists the other membership mode. */
export function LibrarySwitcher({ staff = false, compact = false }: { staff?: boolean; compact?: boolean }) {
  const state = useInstitutionStore(), navigate = useNavigate()
  const libraries = state.libraries.filter(l => staff ? isLibraryStaff(l) : libraryRole(l) === 'GENERAL_USER')
  const selected = staff ? state.staffLibraryId : state.patronLibraryId
  return <label className="workspace-switcher">{!compact && (staff ? 'Staff library' : 'Patron library')}<select aria-label={staff ? 'Switch staff library' : 'Switch patron library'} value={selected || ''} disabled={state.loading || libraries.length < 2} onChange={e => { const row = libraries.find(l => l.library_id === e.target.value); if (row) navigate(libraryWorkspaceHome(row)) }}>
    {!selected && <option value="">Choose a library</option>}{libraries.map(l => <option key={l.library_id} value={l.library_id}>{l.name}</option>)}
  </select></label>
}
