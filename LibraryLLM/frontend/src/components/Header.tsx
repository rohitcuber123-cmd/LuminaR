import { useProductContext } from '../hooks/useProductContext'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Search, Bookmark, Menu, BookOpen } from 'lucide-react'
import { useLibraryStore } from '../store/useLibraryStore'
import { useAuthStore } from '../store/useAuthStore'
import { patronLibrary, useInstitutionStore } from '../store/useInstitutionStore'
import { libraryRole, patronPath } from '../lib/libraryWorkspace'
import { useEventStore } from '../store/useEventStore'
import { NotificationCenter } from './NotificationCenter'
import { AccountMenu } from './AccountMenu'
import { Modal } from './StaffUI'

const links = [{ label: 'Graph Lab', to: '/experimental/kg' }, { label: 'Catalog', to: '/catalog' }, { label: 'New Arrivals', to: '/#new-arrivals' }, { label: 'Events', to: '/events' }, { label: 'About', to: '/#about' }, { label: 'Know More', to: '/llm' }]
export function Header() {
  const [menuOpen, setMenuOpen] = useState(false), [searchOpen, setSearchOpen] = useState(false), [search, setSearch] = useState('')
  const { isAuthenticated, user, token } = useAuthStore(), memberships = useInstitutionStore(), navigate = useNavigate()
  const readingListCount = useLibraryStore(s => s.readingList.length), eventCount = useEventStore(s => s.scope === token ? s.count : 0)
  const patrons = memberships.session === token ? memberships.libraries.filter(l => libraryRole(l) === 'GENERAL_USER') : []
  const selectedPatron = patronLibrary(memberships)
  const context = useProductContext(), scopedPatronId = context.libraryId
  const scopedPatron = patrons.find(l => l.library_id === scopedPatronId)
  const catalogueLinks = links.map(link => link.label === 'Events' ? { ...link, to: context.eventsPath } : link.label === 'Catalog' ? { label: scopedPatronId ? 'Browse Books' : 'Catalog', to: context.cataloguePath } : link.label === 'New Arrivals' ? { ...link, to: context.newArrivalsPath } : { ...link, to: context.personalPath(link.to) })
  const navLinks = context.kind==='PLATFORM' ? [{label:'Overview',to:'/platform'},{label:'Libraries',to:'/platform/libraries'}] : [...catalogueLinks, ...(scopedPatronId || patrons.length ? [{ label: 'My Library', to: scopedPatronId ? patronPath(scopedPatronId, 'my-library') : selectedPatron ? patronPath(selectedPatron.library_id, 'my-library') : patrons.length === 1 ? patronPath(patrons[0].library_id, 'my-library') : '/account/libraries?group=patron' }] : [])]
  const navigation = (mobile = false) => navLinks.map(link => <Link key={link.to} to={link.to} onClick={() => { if (mobile) setMenuOpen(false) }} aria-label={link.label === 'Events' && eventCount ? `Events, ${eventCount} new` : undefined}>{link.label}{link.label === 'Events' && eventCount > 0 && <span className="global-count" aria-hidden="true">{eventCount > 9 ? '9+' : eventCount}</span>}</Link>)
  return <header className="global-header"><a className="ui-skip-link" href="#main-content">Skip to content</a><div className="global-header-inner"><Link to={context.homePath} className="global-logo" aria-label="LuminaR home"><BookOpen size={20} strokeWidth={1.75} /><span>Lumina<span>R</span></span></Link><nav className="global-desktop-nav" aria-label="LuminaR navigation">{navigation()}</nav><div className="global-header-actions">
    {isAuthenticated && user && <NotificationCenter key={`notifications:${user.user_id ?? user.id}`} />}
    <button className="global-search-toggle" aria-label="Search the catalog" aria-expanded={searchOpen} onClick={() => setSearchOpen(v => !v)}><Search size={18} /><span>Search</span></button>
    <Link to={context.personalPath('/reading-list')} className="global-saved" aria-label="My reading list"><Bookmark size={19} />{readingListCount > 0 && <span className="global-count">{readingListCount}</span>}</Link>
    {isAuthenticated && user ? <AccountMenu key={`account:${user.user_id ?? user.id}`} /> : <div className="global-auth"><Link to="/login">Sign In</Link><Link className="ui-button" to="/signup">Create Account</Link></div>}
    <button className="global-mobile-toggle" aria-label="Toggle menu" aria-haspopup="dialog" aria-expanded={menuOpen} onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
  </div></div>{searchOpen && <form className="global-search" onSubmit={e => { e.preventDefault(); if (search.trim()) { navigate(context.searchPath(search.trim())); setSearchOpen(false); setSearch('') } }}><label htmlFor="header-catalog-search">{scopedPatronId ? `Search catalogue for ${scopedPatron?.name || 'this library'}` : context.staffLibraryId ? 'Search this library collection' : 'Search the global catalogue'}</label><input id="header-catalog-search" type="search" value={search} onChange={e => setSearch(e.target.value)} autoFocus /><button type="submit" className="ui-button">Search</button></form>}
    {menuOpen && <Modal title="LuminaR navigation" className="global-nav-dialog" onClose={() => setMenuOpen(false)}><nav aria-label="Mobile LuminaR navigation">{navigation(true)}{!isAuthenticated && <><Link to="/login" onClick={() => setMenuOpen(false)}>Sign In</Link><Link to="/signup" onClick={() => setMenuOpen(false)}>Create Account</Link></>}</nav></Modal>}
  </header>
}
