import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Search,
  Bookmark,
  Menu,
  X,
  BookOpen,
  LogIn,
  LogOut,
  User,
  ChevronDown,
  Shield,
  Library,
} from 'lucide-react'

import { useLibraryStore } from '@/store/useLibraryStore'
import { useAuthStore } from '@/store/useAuthStore'
import { NotificationCenter } from './NotificationCenter'


const NAV_LINKS: {
  label: string
  to: string
}[] = [
  { label: 'Graph Lab', to: '/experimental/kg' },
  {
    label: 'Catalog',
    to: '/catalog',
  },
  {
    label: 'New Arrivals',
    to: '/#new-arrivals',
  },
  {
    label: 'Events',
    to: '/#events',
  },
  {
    label: 'About',
    to: '/#about',
  },
  {
    label: 'KNOW MORE',
    to: '/llm',
  },
]



export function Header() {

  const [menuOpen, setMenuOpen] =
    useState(false)

  const [searchOpen, setSearchOpen] =
    useState(false)

  const [localSearch, setLocalSearch] =
    useState('')

  const [userMenuOpen, setUserMenuOpen] =
    useState(false)

  const navigate =
    useNavigate()


  const readingListCount =
    useLibraryStore(
      (s) => s.readingList.length
    )


  const {
    isAuthenticated,
    user,
    logout,
  } = useAuthStore()


  function handleSearch(
    e: React.FormEvent
  ) {

    e.preventDefault()

    if (localSearch.trim()) {

      navigate(`/search?q=${encodeURIComponent(localSearch.trim())}`)

      setSearchOpen(false)

      setLocalSearch('')
    }
  }


  async function handleLogout() {
    await logout()
    setUserMenuOpen(false)
    setMenuOpen(false)
    navigate('/login')
  }


  // Build role-specific nav links
  const roleLinks: { label: string; to: string; icon: React.ReactNode }[] = []

  if (user?.role === 'GENERAL_USER') {
    roleLinks.push({ label: 'My Library', to: '/profile', icon: <User className="h-3.5 w-3.5" /> })
  }

  if (user?.role === 'ADMIN') {
    roleLinks.push({
      label: 'Admin Dashboard',
      to: '/admin',
      icon: <Shield className="h-3.5 w-3.5" />,
    })
  }

  if (user?.role === 'LIBRARIAN' || user?.role === 'ADMIN') {
    roleLinks.push({
      label: 'Librarian Dashboard',
      to: '/librarian',
      icon: <Library className="h-3.5 w-3.5" />,
    })
  }

  // Staff-only links for the user dropdown menu to avoid duplicating "My Library"
  const staffRoleLinks = roleLinks.filter((link) => link.to !== '/profile')


  return (

    <header
      className="
        sticky
        top-0
        z-50
        border-b
        border-line
        bg-paper/95
        backdrop-blur
      "
    >

      {/* MAIN HEADER */}

      <div
        className="
          relative
          mx-auto
          flex
          h-[72px]
          max-w-[90rem]
          items-center
          justify-between
          px-6
          md:px-10
        "
      >

        {/* LOGO */}

        <Link
          to="/"
          className="
            flex
            items-center
            gap-2
          "
        >

          <BookOpen
            className="
              h-5
              w-5
              text-brand
            "
            strokeWidth={1.75}
          />

          <span
            className="
              font-display
              text-[1.15rem]
              tracking-tight
              text-ink
            "
          >
            Lumina

            <span
              className="text-brand"
            >
              R
            </span>

          </span>

        </Link>


        {/* DESKTOP NAVIGATION */}

        <nav
          className="
            absolute
            left-1/2
            -translate-x-1/2
            hidden
            items-center
            gap-4
            xl:flex
          "
        >

          {NAV_LINKS.map(
            (link) => (

              <Link
                key={link.label}
                to={link.to}

                className="
                  font-display
                  text-[0.72rem]
                  tracking-wide
                  text-ink-soft
                  transition-colors
                  hover:text-brand
                "
              >
                {link.label}
              </Link>

            )
          )}

          {/* Role-specific desktop nav links */}
          {roleLinks.map(
            (link) => (

              <Link
                key={link.label}
                to={link.to}

                className="
                  font-display
                  text-[0.72rem]
                  tracking-wide
                  text-brand
                  transition-colors
                  hover:text-brand-dark
                "
              >
                {link.label}
              </Link>

            )
          )}

        </nav>


        {/* RIGHT SIDE ACTIONS */}

        <div
          className="
            flex
            items-center
            gap-3 sm:gap-5
          "
        >

          {/* SEARCH */}
          {isAuthenticated && user && <NotificationCenter key={String(user.user_id ?? user.id)} />}

          <button
            aria-label="Search the catalog"

            onClick={() =>
              setSearchOpen(
                (v) => !v
              )
            }

            className="
              flex
              items-center
              gap-2
              text-ink-soft
              transition-colors
              hover:text-ink
            "
          >

            <Search
              className="
                h-[18px]
                w-[18px]
              "
              strokeWidth={1.75}
            />

            <span
              className="
                hidden
                text-[0.8rem]
                sm:inline
              "
            >
              Search
            </span>

          </button>


          {/* READING LIST */}

          <Link
            to="/reading-list"

            aria-label="My reading list"

            className="
              relative
              flex
              items-center
              text-ink-soft
              transition-colors
              hover:text-ink
            "
          >

            <Bookmark
              className="
                h-[19px]
                w-[19px]
              "
              strokeWidth={1.75}
            />


            {readingListCount > 0 && (

              <span
                className="
                  absolute
                  -right-2
                  -top-2
                  flex
                  h-4
                  min-w-4
                  items-center
                  justify-center
                  rounded-full
                  bg-brand
                  px-1
                  text-[0.6rem]
                  font-medium
                  text-paper
                "
              >
                {readingListCount}
              </span>

            )}

          </Link>


          {/* AUTH ACTIONS */}

          {isAuthenticated && user ? (

            /* ── Logged-in user menu ── */
            <div className="relative">

              <button
                onClick={() => setUserMenuOpen((v) => !v)}
                className="
                  flex
                  items-center
                  gap-2
                  rounded-full
                  border
                  border-line
                  py-1.5
                  pl-2
                  pr-3
                  text-ink-soft
                  transition-colors
                  hover:border-brand/30
                  hover:text-ink
                "
              >
                <span
                  className="
                    flex
                    h-6
                    w-6
                    items-center
                    justify-center
                    rounded-full
                    bg-brand/10
                    text-brand
                  "
                >
                  <User className="h-3.5 w-3.5" />
                </span>

                <span className="hidden max-w-[8rem] truncate text-[0.78rem] font-medium sm:inline">
                  {user.name || user.full_name || user.email}
                </span>

                <ChevronDown className="h-3 w-3 text-ink-soft/60" />
              </button>


              {/* Dropdown menu */}
              {userMenuOpen && (
                <>
                  {/* Invisible backdrop to close menu */}
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setUserMenuOpen(false)}
                  />

                  <div
                    className="
                      absolute
                      right-0
                      top-full
                      z-50
                      mt-2
                      w-56
                      overflow-hidden
                      rounded-xl
                      border
                      border-line
                      bg-paper
                      shadow-lg
                      shadow-ink/5
                    "
                  >
                    {/* User info */}
                    <div className="border-b border-line px-4 py-3">
                      <p className="truncate text-sm font-medium text-ink">
                        {user.name || user.full_name || 'User'}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-ink-soft">
                        {user.email}
                      </p>
                      {user.role && user.role !== 'GENERAL_USER' && (
                        <span className="mt-1.5 inline-block rounded-full bg-brand/10 px-2 py-0.5 text-[0.6rem] font-medium uppercase tracking-wider text-brand">
                          {user.role.replace('_', ' ')}
                        </span>
                      )}
                    </div>

                    {/* Staff role links */}
                    {staffRoleLinks.length > 0 && (
                      <div className="border-b border-line py-1">
                        {staffRoleLinks.map((link) => (
                          <Link
                            key={link.to}
                            to={link.to}
                            onClick={() => setUserMenuOpen(false)}
                            className="flex items-center gap-2.5 px-4 py-2 text-sm text-ink-soft transition-colors hover:bg-panel hover:text-brand"
                          >
                            {link.icon}
                            {link.label}
                          </Link>
                        ))}
                      </div>
                    )}

                    {/* Profile and Logout */}
                    <div className="py-1">
                      <Link
                        to="/profile"
                        onClick={() => setUserMenuOpen(false)}
                        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-ink-soft transition-colors hover:bg-panel hover:text-brand"
                      >
                        <User className="h-3.5 w-3.5" />
                        My Library
                      </Link>
                      
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-ink-soft transition-colors hover:bg-panel hover:text-brand"
                      >
                        <LogOut className="h-3.5 w-3.5" />
                        Sign Out
                      </button>
                    </div>
                  </div>
                </>
              )}

            </div>

          ) : (

            /* ── Logged-out auth links ── */
            <div className="hidden items-center gap-4 sm:flex">

              <Link
                to="/login"
                className="
                  font-display
                  text-[0.72rem]
                  tracking-wide
                  text-ink-soft
                  transition-colors
                  hover:text-brand
                "
              >
                Sign In
              </Link>

              <Link
                to="/signup"
                className="
                  rounded-lg
                  bg-brand
                  px-4
                  py-2
                  font-display
                  text-[0.72rem]
                  tracking-wide
                  text-paper
                  transition-colors
                  hover:bg-brand-dark
                "
              >
                Create Account
              </Link>

            </div>

          )}


          {/* MOBILE MENU BUTTON */}

          <button
            aria-label="Toggle menu"

            onClick={() =>
              setMenuOpen(
                (v) => !v
              )
            }

            className="
              text-ink-soft
              transition-colors
              hover:text-ink
              xl:hidden
            "
          >

            {menuOpen ? (

              <X
                className="
                  h-5
                  w-5
                "
              />

            ) : (

              <Menu
                className="
                  h-5
                  w-5
                "
              />

            )}

          </button>

        </div>

      </div>


      {/* SEARCH PANEL */}

      {searchOpen && (

        <div
          className="
            border-t
            border-line
            bg-panel
            px-6
            py-4
            md:px-10
          "
        >

          <form
            onSubmit={handleSearch}

            className="
              mx-auto
              flex
              max-w-[90rem]
              items-center
              gap-3
            "
          >

            <Search
              className="
                h-4
                w-4
                shrink-0
                text-ink-soft
              "
            />


            <input
              autoFocus
              type="text"

              value={localSearch}

              onChange={(e) =>
                setLocalSearch(
                  e.target.value
                )
              }

              placeholder="
                Search by title, author, or ISBN...
              "

              className="
                w-full
                bg-transparent
                text-sm
                text-ink
                placeholder:text-ink-soft/60
                focus:outline-none
              "
            />


            {localSearch && (

              <button
                type="button"

                onClick={() =>
                  setLocalSearch('')
                }

                className="
                  text-ink-soft
                  hover:text-ink
                "
              >

                <X
                  className="
                    h-4
                    w-4
                  "
                />

              </button>

            )}

          </form>

        </div>

      )}


      {/* MOBILE NAVIGATION */}

      {menuOpen && (

        <nav
          className="
            flex
            flex-col
            border-t
            border-line
            bg-paper
            px-6
            py-4
            xl:hidden
          "
        >

          {NAV_LINKS.map(
            (link) => (

              <Link
                key={link.label}

                to={link.to}

                onClick={() =>
                  setMenuOpen(false)
                }

                className="
                  font-display
                  border-b
                  border-line
                  py-3
                  text-sm
                  tracking-wide
                  text-ink-soft
                  last:border-none
                  hover:text-brand
                "
              >

                {link.label}

              </Link>

            )
          )}

          {/* Role links in mobile */}
          {roleLinks.map(
            (link) => (

              <Link
                key={link.label}

                to={link.to}

                onClick={() =>
                  setMenuOpen(false)
                }

                className="
                  font-display
                  border-b
                  border-line
                  py-3
                  text-sm
                  tracking-wide
                  text-brand
                  last:border-none
                  hover:text-brand-dark
                "
              >

                {link.label}

              </Link>

            )
          )}

          {/* Mobile auth actions */}
          <div className="mt-2 flex flex-col gap-1 border-t border-line pt-3 sm:hidden">
            {isAuthenticated && user ? (

              <>
                <div className="px-1 py-2">
                  <p className="text-sm font-medium text-ink">
                    {user.name || user.full_name || user.email}
                  </p>
                  {user.role && user.role !== 'GENERAL_USER' && (
                    <span className="mt-1 inline-block rounded-full bg-brand/10 px-2 py-0.5 text-[0.6rem] font-medium uppercase tracking-wider text-brand">
                      {user.role.replace('_', ' ')}
                    </span>
                  )}
                </div>

                <button
                  onClick={handleLogout}
                  className="
                    flex
                    items-center
                    gap-2
                    font-display
                    py-3
                    text-sm
                    tracking-wide
                    text-ink-soft
                    hover:text-brand
                  "
                >
                  <LogOut className="h-4 w-4" />
                  Sign Out
                </button>
              </>

            ) : (

              <>
                <Link
                  to="/login"
                  onClick={() => setMenuOpen(false)}
                  className="
                    flex
                    items-center
                    gap-2
                    font-display
                    py-3
                    text-sm
                    tracking-wide
                    text-ink-soft
                    hover:text-brand
                  "
                >
                  <LogIn className="h-4 w-4" />
                  Sign In
                </Link>

                <Link
                  to="/signup"
                  onClick={() => setMenuOpen(false)}
                  className="
                    flex
                    items-center
                    gap-2
                    font-display
                    py-3
                    text-sm
                    tracking-wide
                    text-ink-soft
                    hover:text-brand
                  "
                >
                  <User className="h-4 w-4" />
                  Create Account
                </Link>
              </>

            )}
          </div>

        </nav>

      )}

    </header>
  )
}
