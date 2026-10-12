import { useProductContext } from '../hooks/useProductContext'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut, User, ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { platformAdmin, usePlatformStore } from '../store/usePlatformStore'
import { useAuthStore } from '../store/useAuthStore'
import { useInstitutionStore } from '../store/useInstitutionStore'
import { isLibraryStaff, libraryRole, libraryWorkspaceHome, membershipLabel } from '../lib/libraryWorkspace'
import { Modal } from './StaffUI'
import { menuKeys } from '../lib/menuKeyboard'

const menuLimit = 3
export function AccountMenu() {
  const context=useProductContext()
  const [open, setOpen] = useState(false), navigate = useNavigate()
  const { user, logout, token } = useAuthStore(), state = useInstitutionStore(), canManagePlatform = platformAdmin(usePlatformStore(), token)
  if (!user) return null
  const libraries = state.session === token ? state.libraries : []
  const patrons = libraries.filter(l => libraryRole(l) === 'GENERAL_USER'), staff = libraries.filter(isLibraryStaff)
  const link = (to: string, text: React.ReactNode, focus = false) => <Link to={context.personalPath(to)} role="menuitem" data-autofocus={focus || undefined} onClick={() => setOpen(false)}>{text}</Link>
  return <><button className="account-trigger" aria-label={`Open account menu for ${user.name || user.full_name || user.email}`} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? 'account-library-menu' : undefined} onClick={() => { setOpen(true); void state.refresh() }}><span className="account-avatar"><User size={16} /></span><span className="account-trigger-name">{user.name || user.full_name || user.email}</span><ChevronDown size={13} /></button>
    {open && <Modal title="Account & libraries" className="account-dialog" onClose={() => setOpen(false)}><div className="account-menu-identity"><strong>{user.name || user.full_name || 'Your account'}</strong><span>{user.email}</span></div><div id="account-library-menu" role="menu" aria-label="Account and library navigation" onKeyDown={menuKeys}>
      <section role="group" aria-labelledby="menu-account-title"><h3 id="menu-account-title">My account</h3>{link('/account/profile', 'Profile', true)}{link('/reading-list', 'Saved / Reading list')}{link('/account/libraries', 'My libraries')}</section>
      {canManagePlatform && <section role="group" aria-labelledby="menu-platform-title"><h3 id="menu-platform-title">Platform</h3>{link('/platform', 'Platform Administration')}</section>}<section role="group" aria-labelledby="menu-patron-title"><h3 id="menu-patron-title">My patron libraries</h3>{patrons.slice(0, menuLimit).map(l => <Link key={l.library_id} to={libraryWorkspaceHome(l)} role="menuitem" onClick={() => setOpen(false)}><span>{l.name}</span><span className="ui-badge">Member</span></Link>)}{!patrons.length && <p className="ui-menu-empty">{state.loading ? 'Loading memberships…' : 'No member libraries yet.'}</p>}{patrons.length > menuLimit && link('/account/libraries?group=patron', 'View all patron libraries')}</section>
      <section role="group" aria-labelledby="menu-staff-title"><h3 id="menu-staff-title">Staff workspaces</h3>{staff.slice(0, menuLimit).map(l => <Link key={l.library_id} to={libraryWorkspaceHome(l)} role="menuitem" onClick={() => setOpen(false)}><span>{l.name}</span><span className="ui-badge">{membershipLabel(l)}</span></Link>)}{!staff.length && <p className="ui-menu-empty">{state.loading ? 'Loading memberships…' : 'No staff workspaces yet.'}</p>}{staff.length > menuLimit && link('/account/libraries?group=staff', 'View all staff workspaces')}</section>
      <section role="group" aria-label="Library discovery">{link('/invitations', 'Pending Invitations')}{link('/libraries', 'Explore Libraries')}{link('/libraries/register', 'Register a Library')}{libraries.length > menuLimit && link('/account/libraries', 'View all libraries')}</section>
      <button role="menuitem" className="ui-menu-signout" onClick={async () => { await logout(); useInstitutionStore.getState().reset(); usePlatformStore.getState().reset(); setOpen(false); navigate('/login') }}><LogOut size={16} />Sign Out</button>
    </div></Modal>}
  </>
}
