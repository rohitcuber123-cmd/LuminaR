import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom'
import { BookOpen, ClipboardList, Home, Users, Settings, History, Menu, ListOrdered, Receipt, CalendarDays, ChartNoAxesCombined, Files } from 'lucide-react'
import { activeLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { useAuthStore } from '../store/useAuthStore'
import { institutionApi, type Page, type MemberRow } from '../lib/institutions'
import { libraryRole, membershipLabel, patronPath, staffPath } from '../lib/libraryWorkspace'
import type { InventoryPage } from '../lib/libraryInventory'
import type { LendingPage } from '../lib/libraryLending'
import { BORROW_STATE_CHANGED } from '../lib/api'
import { LibrarySwitcher } from './LibrarySwitcher'
import { Modal } from './StaffUI'
import { PageHeading, StatePanel } from './WorkspaceUI'
import { catalogueBase, type CatalogueSource } from '../lib/libraryCatalogue'
import { observeCatalogue } from '../lib/catalogueInvalidation'

type Summary = { books: number; pendingBorrow: number | null; pendingReturn: number | null; loans: number | null; members: number | null; mode: string; catalogue: CatalogueSource | null }
type SummaryContext = { summary: Summary | null; error: string; retry: () => void }
export function StaffLibraryShell() {
  const library = useInstitutionStore(activeLibrary), token = useAuthStore(s => s.token), location = useLocation()
  const [drawer, setDrawer] = useState(false), [revision, setRevision] = useState(0)
  const [result, setResult] = useState<{ key: string; data?: Summary; error?: string } | null>(null)
  const id = library?.library_id || '', admin = libraryRole(library) === 'ADMIN', key = `${id}:${token}:${admin}:${revision}:${location.pathname}`
  useEffect(() => {
    let alive = true; const controller = new AbortController()
    async function load() {
      try {
        const [inventory, config, source] = await Promise.all([institutionApi<InventoryPage>(`/libraries/${id}/inventory/books?state=all&limit=1`, 'GET', undefined, controller.signal), institutionApi<{ state: string }>(`/libraries/${id}/lending/config`, 'GET', undefined, controller.signal), institutionApi<CatalogueSource>(`${catalogueBase(id)}/source?staff=true`, 'GET', undefined, controller.signal).catch(() => null)])
        const canonical = config.state === 'CANONICAL'
        const [queue, loans, members] = await Promise.all([
          canonical ? institutionApi<LendingPage>(`/libraries/${id}/staff/lending/borrow-requests?limit=1`, 'GET', undefined, controller.signal) : null,
          canonical ? institutionApi<LendingPage>(`/libraries/${id}/staff/loans?status=ACTIVE&limit=1`, 'GET', undefined, controller.signal) : null,
          admin ? institutionApi<Page<MemberRow>>(`/libraries/${id}/memberships?limit=1`, 'GET', undefined, controller.signal) : null,
        ])
        if (alive) setResult({ key, data: { books: inventory.total, pendingBorrow: queue?.pending_counts?.BORROW ?? null, pendingReturn: queue?.pending_counts?.RETURN ?? null, loans: loans?.total ?? null, members: members?.total ?? null, mode: config.state, catalogue: source?.library_id === id ? source : null } })
      } catch (reason) { if (alive) setResult({ key, error: reason instanceof Error ? reason.message : 'Unable to load library overview.' }) }
    }
    if (id) void load()
    return () => { alive = false; controller.abort() }
  }, [id, admin, key])
  useEffect(() => { const refresh = () => setRevision(r => r + 1); window.addEventListener(BORROW_STATE_CHANGED, refresh); return () => window.removeEventListener(BORROW_STATE_CHANGED, refresh) }, [])
  useEffect(() => observeCatalogue(id, () => setRevision(r => r + 1)), [id])
  if (!library) return <StatePanel title="Loading staff workspace…" kind="loading" />
  const summary = result?.key === key ? result.data || null : null, error = result?.key === key ? result.error || '' : ''
  const pending = summary?.pendingBorrow == null || summary.pendingReturn == null ? null : summary.pendingBorrow + summary.pendingReturn
  const sections = [{ label: 'Overview', path: '', icon: Home }, { label: 'Catalog', path: 'catalogue', icon: BookOpen }, { label: 'Inventory', path: 'inventory', icon: BookOpen }, { label: 'Circulation', path: 'circulation', icon: ClipboardList }, { label: 'Reservations', path: 'reservations', icon: ListOrdered }, { label: 'Fees', path: 'fees', icon: Receipt }, { label: 'Events', path: 'events', icon: CalendarDays }, { label: 'Analytics', path: 'analytics', icon: ChartNoAxesCombined }, { label: 'Digital Assets', path: 'assets', icon: Files }, { label: 'Intelligence', path: 'intelligence', icon: ChartNoAxesCombined }, ...(admin ? [{ label: 'Members & Staff', path: 'members', icon: Users }] : []), { label: 'Operational Activity', path: 'activity', icon: History }, { label: 'Library Settings', path: 'settings', icon: Settings }, ...(admin ? [{ label: 'Audit / Activity', path: 'audit', icon: History }] : [])]
  const navigation = (mobile = false) => <nav aria-label={mobile ? 'Mobile staff workspace' : 'Staff workspace'}>{sections.map(({ label, path, icon: Icon }) => <NavLink key={path} to={staffPath(id, path)} end={!path} onClick={() => { if (mobile) setDrawer(false) }}><Icon size={17} aria-hidden="true" />{label}{path === 'circulation' && pending != null && pending > 0 && <span className="workspace-nav-count" aria-label={`${pending} pending requests`}>{pending}</span>}</NavLink>)}</nav>
  const identity = <div className="workspace-identity"><p className="ui-eyebrow">Staff workspace</p><h2>{library.name}</h2><span className="ui-badge">{membershipLabel(library)}</span><LibrarySwitcher staff /></div>
  const current = sections.find(s => location.pathname === staffPath(id, s.path))?.label || 'Workspace'
  return <div className="workspace staff-workspace"><aside className="workspace-sidebar" aria-label="Library management">{identity}{navigation()}</aside><div className="workspace-mobile-header"><div><strong>{library.name}</strong><span className="ui-badge">{membershipLabel(library)}</span></div><button aria-label="Open workspace menu" aria-haspopup="dialog" aria-expanded={drawer} onClick={() => setDrawer(true)}><Menu size={18} />Menu</button></div><section className="workspace-content"><div className="workspace-breadcrumb" role="navigation" aria-label="Breadcrumb"><Link to={staffPath(id)}>{library.name}</Link><span aria-hidden="true">/</span><span>{current}</span></div><Outlet context={{ summary, error, retry: () => setRevision(r => r + 1) } satisfies SummaryContext} /></section>{drawer && <Modal title="Workspace menu" className="workspace-nav-dialog" onClose={() => setDrawer(false)}>{identity}{navigation(true)}</Modal>}</div>
}
export function StaffCatalogueSummary({ source, retry }: { source: CatalogueSource | null; retry: () => void }) {
  return <section className="ui-card workspace-catalogue-summary"><h2>Collection</h2>{source ? <><p>{source.local_book_count.toLocaleString()} local books</p><h3>{source.catalogue_source === 'LIBRARY_LOCAL' ? 'Catalogue' : 'Discovery fallback'}</h3><p>{source.catalogue_source === 'LIBRARY_LOCAL' ? 'Library collection' : 'LuminaR global catalogue'}</p></> : <p>Catalogue status unavailable. <button onClick={retry}>Retry</button></p>}</section>
}
export function StaffOverviewPage() {
  const library = useInstitutionStore(activeLibrary)!, { summary, error, retry } = useOutletContext<SummaryContext>()
  return <div className="institutions"><PageHeading title="Overview" description={`Manage ${library.name}'s collection, circulation and library settings.`} />{error ? <StatePanel title="Unable to load overview" kind="error" action={<button onClick={retry}>Retry</button>}>{error}</StatePanel> : !summary ? <StatePanel title="Loading library overview…" kind="loading" /> : <><StaffCatalogueSummary source={summary.catalogue} retry={retry} /><div className="workspace-stat-grid">{[{ label: 'Inventory records', value: summary.books }, { label: 'Pending borrow requests', value: summary.pendingBorrow }, { label: 'Pending return requests', value: summary.pendingReturn }, { label: 'Current loans', value: summary.loans }].map(card => <div className="ui-card" key={card.label}><span>{card.label}</span>{card.value == null ? <span className="ui-badge workspace-status">Setup required</span> : <strong>{card.value}</strong>}</div>)}</div>{summary.books === 0 && <section className="ui-card workspace-welcome"><h2>Welcome to {library.name}.</h2><p>Start with your first book or upload your library inventory. Staff review borrow requests and confirm physical returns in Circulation.</p><div className="ui-actions"><Link className="ui-button" to={staffPath(library.library_id, 'inventory?action=add')}>Add first book</Link><Link className="ui-button ui-secondary" to={staffPath(library.library_id, 'inventory?action=import')}>Upload inventory</Link>{libraryRole(library) === 'ADMIN' && <Link className="ui-button ui-secondary" to={staffPath(library.library_id, 'members')}>Invite librarian</Link>}</div></section>}<section className="ui-card"><h2>Quick actions</h2><div className="ui-actions"><Link className="ui-button" to={staffPath(library.library_id, 'inventory?action=add')}>Add Book</Link><Link className="ui-button ui-secondary" to={staffPath(library.library_id, 'inventory?action=import')}>Upload Inventory</Link><Link className="ui-button ui-secondary" to={staffPath(library.library_id, 'circulation')}>Review Borrow Requests</Link><Link className="ui-button ui-secondary" to={staffPath(library.library_id, 'circulation?tab=return')}>Review Returns</Link>{summary.members != null && <Link to={staffPath(library.library_id, 'members')}>{summary.members} memberships · Manage staff</Link>}</div></section></>}</div>
}
export function PatronLibraryShell() {
  const library = useInstitutionStore(activeLibrary)
  const location = useLocation()
  if (!library) return <StatePanel title="Loading patron workspace…" kind="loading" />
  const id = library.library_id
  const activity = /\/(my-library|loans|reservations|fees)$/.test(location.pathname)
  return <div className="patron-workspace"><div className="patron-context-bar">
    <Link to={patronPath(id)} className="patron-context-name">{library.name}</Link>
    <span className="patron-context-membership">Member · {library.access_mode === 'PUBLIC' ? 'Public library' : 'Private institution'}</span>
    <nav aria-label="Library activity" className="patron-context-links"><Link to={patronPath(id, 'my-library')}>My Library</Link><Link to={patronPath(id, 'reservations')}>Reservations</Link><Link to={patronPath(id, 'fees')}>Fees</Link><Link to={patronPath(id, 'resources')}>Resources</Link></nav>
    <LibrarySwitcher compact />
  </div><div className={activity ? 'workspace patron-activity' : undefined}><Outlet /></div></div>
}
