import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { StaffActivity } from '../src/components/StaffActivityTable'
registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html lang="en"><head><title>Activity tests</title></head><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor, within } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { StaffActivityTable } = await import('../src/components/StaffActivityTable.tsx')
const { LibraryActivityPage } = await import('../src/pages/LibraryActivity.tsx')
const { InstitutionPanel } = await import('../src/pages/InstitutionPanel.tsx')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const id = '11111111-1111-4111-8111-111111111111', reference = '946772b1-4be4-4a32-8435-525e2749ba0f'
function row(patch: Partial<StaffActivity> = {}): StaffActivity { return { event_id: 'fixture-event', event: 'BORROW_REQUEST_APPROVED', created_at: '2026-10-12T12:00:00Z', actor_user_id: 4, target_user_id: 10, actor: { user_id: 4, display_name: 'Librarian', email: 'librarian@example.com', identity_source: 'CURRENT_ACCOUNT' }, member: { user_id: 10, display_name: 'Patron', email: 'patron@example.com', identity_source: 'CURRENT_ACCOUNT' }, metadata: { loan_id: reference }, ...patch } }
let calls: string[], original: typeof fetch
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'activity-fixture')
  auth.setState({ token: 'activity-fixture', isAuthenticated: true, loading: false, user: { user_id: 4, email: 'librarian@example.com', role: 'GENERAL_USER' } })
  const library = { library_id: id, name: 'Fixture library', slug: 'fixture', description: null, access_mode: 'PUBLIC' as const, library_type: 'PUBLIC_LIBRARY' as const, membership: { membership_id: id, library_id: id, user_id: 4, role: 'ADMIN' as const, status: 'ACTIVE' as const, is_owner: true, joined_at: '2026-10-12T00:00:00Z' } }
  store.setState({ owner: 'librarian@example.com', session: 'activity-fixture', activeId: id, libraries: [library], workspace: 'STAFF', loading: false, error: null })
  calls = []; original = globalThis.fetch
  globalThis.fetch = async url => { const path = String(url); calls.push(path); return Response.json(path.endsWith('/access') ? { access_code_set: false } : { results: [row()], total: 42 }) }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
const table = (operational = true, item = row(), onPageChange = (_page: number) => {}) => render(<StaffActivityTable data={{ results: [item], total: 42 }} page={0} onPageChange={onPageChange} operational={operational} />)

test('test_operational_activity_actor_email', async () => { render(<LibraryActivityPage />); await screen.findByText('librarian@example.com'); assert.equal(screen.queryByText('Account #4'), null); assert.equal(screen.queryByText('User #4'), null); assert.ok(calls.every(path => !path.includes('/users/'))) })
test('test_operational_activity_member_email', () => { table(); assert.ok(screen.getByText('patron@example.com')); assert.equal(screen.queryByText('Account #10'), null) })
test('test_audit_actor_email', async () => { render(<MemoryRouter><InstitutionPanel section="audit" /></MemoryRouter>); await screen.findByText('librarian@example.com'); assert.ok(screen.getByRole('table', { name: 'Library audit' })); assert.equal(screen.queryByText('User #4'), null) })
test('test_actor_member_remain_distinct', () => { table(); const cells = within(screen.getAllByRole('row')[1]).getAllByRole('cell'); assert.equal(cells[2].textContent, 'librarian@example.com'); assert.equal(cells[3].textContent, 'patron@example.com') })
test('test_system_actor_label', () => { table(true, row({ actor_user_id: null, actor: null })); assert.ok(screen.getByText('System')); assert.equal(screen.queryByText('Account #null'), null) })
test('test_missing_actor_fallback', () => { table(true, row({ actor_user_id: 999, actor: null })); assert.ok(screen.getByText('Account #999')); assert.ok(screen.getByText('Borrow request approved')) })
test('test_deleted_actor_history_still_renders', () => { table(false, row({ actor: null })); assert.ok(screen.getByText('Account #4')); assert.ok(screen.getByRole('table', { name: 'Library audit' })) })
test('test_activity_reference_full_value_preserved', () => { table(); assert.ok(screen.getByText(reference)); assert.equal(screen.getByText(reference).className, 'sr-only'); assert.ok(screen.getByTitle(reference)) })
test('test_activity_reference_visual_truncation', () => { table(); const short = screen.getByText('946772b1…ba0f'); assert.equal(short.getAttribute('aria-hidden'), 'true'); assert.ok(screen.getByTitle(reference).contains(short)) })
test('test_activity_table_shared_staff_design', () => { table(); const node = screen.getByRole('table', { name: 'Operational activity' }); assert.ok(node.classList.contains('staff-table')); assert.ok(node.classList.contains('staff-activity-table')); assert.ok([...node.querySelectorAll('th')].every(th => th.scope === 'col')); assert.ok(screen.getByTitle('BORROW_REQUEST_APPROVED')) })
test('test_audit_table_shared_staff_design', () => { table(false); const node = screen.getByRole('table', { name: 'Library audit' }); assert.ok(node.classList.contains('staff-table')); assert.ok(node.classList.contains('staff-activity-table')); assert.equal(screen.getAllByRole('columnheader').length, 3) })
test('test_activity_mobile_contained_overflow', () => { table(); const region = screen.getByRole('region', { name: 'Operational activity' }); assert.equal(region.tabIndex, 0); assert.ok(region.classList.contains('staff-table-wrap')); assert.ok(region.contains(screen.getByRole('table'))) })
test('test_activity_pagination_shared_design', () => { let page = 0; table(true, row(), value => { page = value }); const nav = screen.getByRole('navigation', { name: 'Operational activity pagination' }); assert.ok(nav.classList.contains('staff-pager')); assert.ok(within(nav).getByRole('button', { name: 'Previous' }).disabled); fireEvent.click(within(nav).getByRole('button', { name: 'Next' })); assert.equal(page, 1); assert.ok(within(nav).getByText('1–20 of 42')) })
test('test_activity_pagination_preserves_server_page', async () => { render(<LibraryActivityPage />); await screen.findByText('librarian@example.com'); fireEvent.click(screen.getByRole('button', { name: 'Next' })); await waitFor(() => assert.ok(calls.some(path => path.endsWith('offset=20')))); assert.ok(calls.every(path => path.includes('/staff/activity'))) })
