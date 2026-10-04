import assert from 'node:assert/strict'
import test from 'node:test'

import { createReadNowOperation, readNowState } from '../src/lib/readNow.ts'

const policy = (overrides: Partial<Parameters<typeof readNowState>[0]> = {}) => readNowState({
  authenticated: true,
  role: 'GENERAL_USER',
  readable: true,
  borrowed: false,
  accessReady: true,
  borrowAction: 'BORROW',
  ...overrides,
})

test('readable unborrowed borrowable general-user book exposes auto-borrow Read Now', () => {
  assert.equal(policy(), 'AUTO_BORROW')
})

test('an active borrowed readable book opens directly', () => {
  assert.equal(policy({ borrowed: true, borrowAction: 'BORROWED' }), 'DIRECT')
})

test('unreadable, unavailable, reserved, and unborrowed staff books do not expose Read Now', () => {
  assert.equal(policy({ readable: false }), 'HIDDEN')
  assert.equal(policy({ borrowAction: 'RESERVE' }), 'HIDDEN')
  assert.equal(policy({ borrowAction: 'RESERVED' }), 'HIDDEN')
  assert.equal(policy({ role: 'ADMIN' }), 'HIDDEN')
  assert.equal(policy({ role: 'LIBRARIAN' }), 'HIDDEN')
})

test('unauthenticated Read Now requests login and never reports auto-borrow', () => {
  assert.equal(policy({ authenticated: false, role: undefined }), 'LOGIN')
})

test('unborrowed Read Now borrows, refreshes, then opens the exact work_id', async () => {
  const calls: string[] = []
  const run = createReadNowOperation()
  const opened = await run({
    workId: 'OL123W',
    borrowed: false,
    borrow: async workId => { calls.push(`borrow:${workId}`) },
    refresh: async () => { calls.push('refresh:/issues/my') },
    navigate: path => { calls.push(`navigate:${path}`) },
  })
  assert.equal(opened, true)
  assert.deepEqual(calls, [
    'borrow:OL123W',
    'refresh:/issues/my',
    'navigate:/book/OL123W/read',
  ])
})

test('already-borrowed Read Now skips the borrow API and refresh', async () => {
  let borrowCalls = 0
  let refreshCalls = 0
  let path = ''
  await createReadNowOperation()({
    workId: 'OL1W',
    borrowed: true,
    borrow: async () => { borrowCalls += 1 },
    refresh: async () => { refreshCalls += 1 },
    navigate: value => { path = value },
  })
  assert.equal(borrowCalls, 0)
  assert.equal(refreshCalls, 0)
  assert.equal(path, '/book/OL1W/read')
})

test('failed borrowing preserves the safe error and never opens the reader', async () => {
  let navigated = false
  await assert.rejects(createReadNowOperation()({
    workId: 'OL1W',
    borrowed: false,
    borrow: async () => { throw new Error('This title is currently unavailable.') },
    refresh: async () => undefined,
    navigate: () => { navigated = true },
  }), /currently unavailable/)
  assert.equal(navigated, false)
})

test('double click shares an in-flight guard and creates only one borrow attempt', async () => {
  let release!: () => void
  const waiting = new Promise<void>(resolve => { release = resolve })
  let borrowCalls = 0
  let navigateCalls = 0
  const run = createReadNowOperation()
  const operation = {
    workId: 'OL1W',
    borrowed: false,
    borrow: async () => { borrowCalls += 1; await waiting },
    refresh: async () => undefined,
    navigate: () => { navigateCalls += 1 },
  }
  const first = run(operation)
  const second = run(operation)
  assert.equal(await second, false)
  release()
  assert.equal(await first, true)
  assert.equal(borrowCalls, 1)
  assert.equal(navigateCalls, 1)
})

test('Book A operation cannot borrow or open Book B', async () => {
  const ids: string[] = []
  await createReadNowOperation()({
    workId: 'OL-AW',
    borrowed: false,
    borrow: async workId => { ids.push(workId) },
    refresh: async () => undefined,
    navigate: path => { ids.push(path) },
  })
  assert.deepEqual(ids, ['OL-AW', '/book/OL-AW/read'])
})
