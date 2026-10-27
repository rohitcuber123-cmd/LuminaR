import assert from 'node:assert/strict'
import test from 'node:test'
import { destination, workspaceDestination } from '../src/lib/authDestination.ts'
import { getRoleNavLinks } from '../src/lib/nav.ts'
import { BORROW_STATE_CHANGED } from '../src/lib/api.ts'
for (const role of ['ADMIN','LIBRARIAN','GENERAL_USER']) {
 test(`${role} label never chooses management home`, () => assert.equal(destination(role), '/account/continue'))
 test(`${role} label never produces legacy dashboard navigation`, () => assert.deepEqual(getRoleNavLinks(role), [{label:'My Libraries',to:'/account/libraries'}]))
 test(`${role} revalidates explicit workspace deep link`, () => assert.equal(new URLSearchParams(destination(role, '/staff/libraries/explicit/inventory').split('?')[1]).get('return_to'), '/staff/libraries/explicit/inventory'))
}
for (const from of [undefined,'','//evil.invalid','https://evil.invalid','/login','/signup','/staff/login','/dashboard','/account/continue','/\\evil']) test(`safe destination ${String(from)}`,()=>assert.equal(workspaceDestination(from),'/account/continue'))
for (const from of ['/catalog','/search?q=fiction','/book/OL1W','/reading-list','/account/libraries','/platform','/admin','/librarian']) test(`preserves guarded destination ${from}`,()=>assert.equal(workspaceDestination(from),from))
test('anonymous has no account navigation',()=>assert.deepEqual(getRoleNavLinks(undefined),[]))
test('borrow refresh storage key remains stable',()=>assert.ok(BORROW_STATE_CHANGED))
