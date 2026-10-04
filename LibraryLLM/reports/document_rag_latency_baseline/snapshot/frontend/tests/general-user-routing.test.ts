import assert from 'node:assert/strict'
import test from 'node:test'

import { destination } from '../src/lib/authDestination.ts'
import { getRoleNavLinks } from '../src/lib/nav.ts'
import { BORROW_STATE_CHANGED } from '../src/lib/api.ts'
import { readNowState } from '../src/lib/readNow.ts'

// ============================================================
// 1. LOGIN REDIRECTS FOR ALL ROLES
// ============================================================

test('GENERAL_USER login redirects to My Library (/profile)', () => {
  assert.equal(destination('GENERAL_USER'), '/profile')
})

test('ADMIN login redirects to /admin', () => {
  assert.equal(destination('ADMIN'), '/admin')
})

test('LIBRARIAN login redirects to /librarian', () => {
  assert.equal(destination('LIBRARIAN'), '/librarian')
})

test('GENERAL_USER with null/undefined/empty from returns /profile', () => {
  assert.equal(destination('GENERAL_USER', undefined), '/profile')
  assert.equal(destination('GENERAL_USER', ''), '/profile')
  assert.equal(destination('GENERAL_USER', '/login'), '/profile')
})

test('GENERAL_USER with /dashboard from resolves directly to /profile avoiding redirect loops', () => {
  assert.equal(destination('GENERAL_USER', '/dashboard'), '/profile')
})

test('GENERAL_USER cannot redirect to protected staff routes via from', () => {
  assert.equal(destination('GENERAL_USER', '/admin'), '/profile')
  assert.equal(destination('GENERAL_USER', '/admin/users'), '/profile')
  assert.equal(destination('GENERAL_USER', '/librarian'), '/profile')
  assert.equal(destination('GENERAL_USER', '/staff/login'), '/profile')
})

test('GENERAL_USER with valid target path preserves destination', () => {
  assert.equal(destination('GENERAL_USER', '/catalog'), '/catalog')
  assert.equal(destination('GENERAL_USER', '/search?q=fiction'), '/search?q=fiction')
  assert.equal(destination('GENERAL_USER', '/book/OL123W'), '/book/OL123W')
  assert.equal(destination('GENERAL_USER', '/book/OL123W/read'), '/book/OL123W/read')
  assert.equal(destination('GENERAL_USER', '/reading-list'), '/reading-list')
  assert.equal(destination('GENERAL_USER', '/profile'), '/profile')
})

test('Staff roles preserve legitimate deep staff links', () => {
  assert.equal(destination('ADMIN', '/admin'), '/admin')
  assert.equal(destination('ADMIN', '/admin/users'), '/admin/users')
  assert.equal(destination('ADMIN', '/librarian'), '/librarian')
  assert.equal(destination('LIBRARIAN', '/librarian'), '/librarian')
  assert.equal(destination('LIBRARIAN', '/admin'), '/librarian') // LIBRARIAN cannot access /admin
})

// ============================================================
// 2. HEADER & MOBILE NAVIGATION FOR GENERAL_USER & STAFF
// ============================================================

test('GENERAL_USER role nav links contain My Library (/profile)', () => {
  const links = getRoleNavLinks('GENERAL_USER')
  assert.equal(links.length, 1)
  assert.deepEqual(links[0], { label: 'My Library', to: '/profile' })
})

test('GENERAL_USER role nav links do NOT contain Dashboard or My Dashboard', () => {
  const links = getRoleNavLinks('GENERAL_USER')
  assert.equal(links.some(l => l.label.toLowerCase().includes('dashboard')), false)
  assert.equal(links.some(l => l.to === '/dashboard'), false)
})

test('ADMIN role nav links contain Admin Dashboard and Librarian Dashboard', () => {
  const links = getRoleNavLinks('ADMIN')
  assert.deepEqual(links, [
    { label: 'Admin Dashboard', to: '/admin' },
    { label: 'Librarian Dashboard', to: '/librarian' },
  ])
})

test('LIBRARIAN role nav links contain Librarian Dashboard only', () => {
  const links = getRoleNavLinks('LIBRARIAN')
  assert.deepEqual(links, [
    { label: 'Librarian Dashboard', to: '/librarian' },
  ])
})

test('Unauthenticated user has no role-specific nav links', () => {
  assert.deepEqual(getRoleNavLinks(undefined), [])
})

test('Dropdown menu staff filter separates staff links and prevents duplicate My Library', () => {
  // Simulate header dropdown menu filtering logic
  const generalLinks = getRoleNavLinks('GENERAL_USER')
  const generalStaffLinks = generalLinks.filter(l => l.to !== '/profile')
  assert.equal(generalStaffLinks.length, 0, 'GENERAL_USER should have no staff section in dropdown')

  const adminLinks = getRoleNavLinks('ADMIN')
  const adminStaffLinks = adminLinks.filter(l => l.to !== '/profile')
  assert.equal(adminStaffLinks.length, 2, 'ADMIN sees 2 staff links in dropdown')

  const librarianLinks = getRoleNavLinks('LIBRARIAN')
  const librarianStaffLinks = librarianLinks.filter(l => l.to !== '/profile')
  assert.equal(librarianStaffLinks.length, 1, 'LIBRARIAN sees 1 staff link in dropdown')
})

// ============================================================
// 3. PROTECTED ROUTE FALLBACK BEHAVIOR SIMULATION
// ============================================================

function protectedRouteRoleFallback(userRole?: string) {
  return userRole === 'ADMIN'
    ? '/admin'
    : userRole === 'LIBRARIAN'
      ? '/librarian'
      : '/profile'
}

test('Unauthorized ProtectedRoute fallback redirects GENERAL_USER to /profile', () => {
  assert.equal(protectedRouteRoleFallback('GENERAL_USER'), '/profile')
})

test('Unauthorized ProtectedRoute fallback redirects ADMIN to /admin', () => {
  assert.equal(protectedRouteRoleFallback('ADMIN'), '/admin')
})

test('Unauthorized ProtectedRoute fallback redirects LIBRARIAN to /librarian', () => {
  assert.equal(protectedRouteRoleFallback('LIBRARIAN'), '/librarian')
})

test('/dashboard compatibility destination redirects GENERAL_USER to /profile', () => {
  // ReaderDashboard / DashboardRedirect behavior
  assert.equal(protectedRouteRoleFallback('GENERAL_USER'), '/profile')
})

// ============================================================
// 4. READ NOW, KNOW MORE, & BORROW REFRESH INTEGRITY
// ============================================================

test('BORROW_STATE_CHANGED storage key is defined for cross-tab and component sync', () => {
  assert.equal(BORROW_STATE_CHANGED, 'luminar-borrow-state-changed')
})

test('Read Now policy for GENERAL_USER with borrowed book allows DIRECT reading', () => {
  const policy = readNowState({
    authenticated: true,
    role: 'GENERAL_USER',
    readable: true,
    borrowed: true,
    accessReady: true,
    borrowAction: 'BORROWED',
  })
  assert.equal(policy, 'DIRECT')
})

test('Read Now policy for GENERAL_USER with unborrowed readable book allows AUTO_BORROW', () => {
  const policy = readNowState({
    authenticated: true,
    role: 'GENERAL_USER',
    readable: true,
    borrowed: false,
    accessReady: true,
    borrowAction: 'BORROW',
  })
  assert.equal(policy, 'AUTO_BORROW')
})

test('Read Now policy hides reader for staff roles to preserve reader isolation', () => {
  assert.equal(readNowState({ authenticated: true, role: 'ADMIN', readable: true, borrowed: false, accessReady: true, borrowAction: 'BORROW' }), 'HIDDEN')
  assert.equal(readNowState({ authenticated: true, role: 'LIBRARIAN', readable: true, borrowed: false, accessReady: true, borrowAction: 'BORROW' }), 'HIDDEN')
})
