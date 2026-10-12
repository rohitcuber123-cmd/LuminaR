"""Local Part 2E QA through normal APIs and real Chromium; secrets stay in memory."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
prefix = (ROOT / 'scripts/institution_v2d_browser_session.py').read_text(encoding='utf8').split('private_code=')[0]
exec(prefix.replace('v2d', 'v2e').replace('Part 2D', 'Part 2E'), globals())

private_code = secrets.token_urlsafe(20)
for letter, owner, private in [('A', 'owner', True), ('B', 'mixed', False), ('C', 'owner', False), ('EMPTY', 'owner', False)]:
    value = {'name': 'Part 2E QA Library ' + letter, 'slug': f'part2e-{letter.lower()}-{suffix}', 'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY', 'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC'}
    if private:
        value['access_code'] = private_code
    fixtures[letter] = api('/libraries/register', 'POST', value, owner, 201)['library']['library_id']
for user in ['mixed', 'borrower']:
    api(f'/libraries/{fixtures["A"]}/join', 'POST', {'access_code': private_code}, user)
for letter in ['B', 'C']:
    api(f'/libraries/{fixtures[letter]}/join', 'POST', {}, 'borrower')
invite = api(f'/libraries/{fixtures["C"]}/invitations', 'POST', {'email': accounts['mixed']['email'], 'role': 'LIBRARIAN'}, expected=201)
api('/invitations/' + invite['invitation']['invitation_id'] + '/accept', 'POST', {'token': invite['invite_token']}, 'mixed')
for letter, count, owner in [('A', 10, 'owner'), ('B', 4, 'mixed'), ('C', 3, 'owner')]:
    fixtures['books_' + letter] = []
    for number in range(count):
        fields = {'title': f'Part 2E {letter} operational book {number}', 'subjects': ['Community', 'Systems' if number % 2 else 'History'], 'copies': 2 if letter == 'A' and number == 0 else 0 if letter == 'A' and number in [7, 8] else 1}
        if number == 0:
            fields['global_work_id'] = 'OL19313623W'
        if letter == 'A' and number == 9:
            fields['circulation_status'] = 'REFERENCE_ONLY'
        if letter == 'A' and number == 6:
            fields['circulation_status'] = 'TEMPORARILY_UNAVAILABLE'
        created = api(f'/libraries/{fixtures[letter]}/inventory/books', 'POST', cmd(**fields), owner, 201)
        fixtures['books_' + letter].append(created['library_book_id'])
proposal = migration.plan(db, {'platform_assignments': [{'user_id': accounts['platform']['user_id'], 'role': 'PLATFORM_ADMIN', 'approved': True, 'approved_by': 'local-development-review', 'approval_ref': 'USER-INSTITUTION-V2E-QA', 'reason': 'Isolated local analytics lifecycle and Platform-without-membership boundary checks; revoke at cleanup.'}]})
migration.apply(db, proposal)


def borrow(letter, number, patron, owner, approve=True):
    request = api(f'/libraries/{fixtures[letter]}/lending/borrow-requests', 'POST', cmd(library_book_id=fixtures['books_' + letter][number]), patron, 201)
    if not approve:
        return request
    result = api(f'/libraries/{fixtures[letter]}/staff/lending/borrow-requests/{request["lending_request_id"]}/approve', 'POST', cmd(), owner)
    return result['loan']


def seed_activity():
    """Every operation is canonical; only one disposable loan clock is adjusted."""
    fixtures['loans_A'] = []
    for number in [0, 1, 5]:
        fixtures['loans_A'].append(borrow('A', number, 'mixed', 'owner'))
    loan = fixtures['loans_A'][0]
    api(f'/libraries/{fixtures["A"]}/loans/{loan["loan_id"]}/renew', 'POST', cmd(expected_due_at=loan['due_at']), 'mixed')
    loan = fixtures['loans_A'][2]
    api(f'/libraries/{fixtures["A"]}/loans/{loan["loan_id"]}/return-request', 'POST', cmd(), 'mixed', 201)
    borrow('A', 4, 'mixed', 'owner', False)
    rejected = borrow('A', 2, 'mixed', 'owner', False)
    api(f'/libraries/{fixtures["A"]}/staff/lending/borrow-requests/{rejected["lending_request_id"]}/reject', 'POST', cmd(reason='Disposable analytics rejection fixture'), 'owner')
    for number, user in [(7, 'mixed'), (8, 'mixed'), (7, 'borrower')]:
        api(f'/libraries/{fixtures["A"]}/reservations', 'POST', cmd(library_book_id=fixtures['books_A'][number]), user, 201)
    returned = borrow('A', 3, 'mixed', 'owner')
    api(f'/libraries/{fixtures["A"]}/reservations', 'POST', cmd(library_book_id=fixtures['books_A'][3]), 'borrower', 201)
    db.institution_loans.update_one({'library_id': fixtures['A'], 'loan_id': returned['loan_id']}, {'$set': {'due_at': datetime.now(timezone.utc) - timedelta(days=2)}})
    request = api(f'/libraries/{fixtures["A"]}/loans/{returned["loan_id"]}/return-request', 'POST', cmd(), 'mixed', 201)
    api(f'/libraries/{fixtures["A"]}/staff/lending/return-requests/{request["lending_request_id"]}/confirm', 'POST', cmd(), 'owner')
    fee = db.institution_fees.find_one({'library_id': fixtures['A'], 'loan_id': returned['loan_id']})
    assert fee and fee['balance_minor'] == 1000
    api(f'/libraries/{fixtures["A"]}/staff/fees/{fee["fee_id"]}/payments', 'POST', cmd(amount_minor=250, method='CASH', reference='Local analytics QA'), 'owner')
    borrow('B', 0, 'borrower', 'mixed')
    for letter, owner, count in [('A', 'owner', 2), ('B', 'mixed', 1), ('C', 'mixed', 1)]:
        for number in range(count):
            event = api(f'/libraries/{fixtures[letter]}/events', 'POST', {'title': f'Part 2E {letter} upcoming event {number}', 'category': 'OTHER', 'description': 'Canonical local analytics QA event.', 'start_at': (datetime.now(timezone.utc) + timedelta(days=1 + number)).isoformat(), 'visibility': 'LIBRARY_MEMBERS'}, owner, 201)
            api(f'/libraries/{fixtures[letter]}/events/{event["event_id"]}/publish', 'POST', {}, owner)
    event = api(f'/libraries/{fixtures["A"]}/events', 'POST', {'title': 'Part 2E cancelled event', 'category': 'OTHER', 'start_at': (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()}, 'owner', 201)
    api(f'/libraries/{fixtures["A"]}/events/{event["event_id"]}/publish', 'POST', {}, 'owner')
    api(f'/libraries/{fixtures["A"]}/events/{event["event_id"]}/cancel', 'POST', {'reason': 'Disposable analytics cancellation fixture'}, 'owner')
    put('institution_v2e_live_fixture.json', {'status': 'CREATED', 'libraries': {name: fixtures[name] for name in ['A', 'B', 'C', 'EMPTY']}, 'expected_A': {'active_books': 10, 'active_loans': 3, 'pending_borrow': 2, 'pending_return': 1, 'reservations_waiting': 3, 'reservations_ready': 1, 'fee_balance_minor': 750, 'fee_assessed_minor': 1000, 'payment_minor': 250, 'upcoming_events': 2}, 'expected_B': {'active_books': 4, 'active_loans': 1, 'upcoming_events': 1}, 'shared_global_work': 'OL19313623W', 'clock_adjustment': 'Only disposable A loan due_at moved two UTC days before normal physical-return confirmation. No TEST change.'})


base_credentials = credentials


def credentials(account):
    return (accounts[account]['email'], accounts[account]['password']) if account in accounts else base_credentials(account)


def shot(name):
    target = REPORTS / f'institution_v2e_{name}.png'
    page.screenshot(path=str(target), full_page=True, animations='disabled')
    return target.name


normal_login = login


def login(account):
    # Account isolation uses a fresh browser context, then the actual login UI.
    # No token injection, storage-state file or previous account session reuse.
    global context, page
    size = page.viewport_size or {'width': 1440, 'height': 900}
    context.close()
    context = browser.new_context(viewport=size)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: network.append({'path': urlparse(response.url).path, 'status': response.status}) if '/api/' in response.url else None)
    return normal_login(account)


sys.stdout.reconfigure(encoding='utf8')
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    network = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: network.append({'path': urlparse(response.url).path, 'status': response.status}) if '/api/' in response.url else None)
    print(json.dumps({'browser': browser.version, 'fixtures': fixtures, 'QA_accounts': [{'email': row['email'], 'user_id': row['user_id']} for row in accounts.values()]}), flush=True)
    for line in sys.stdin:
        try:
            command = json.loads(line)
            if command.get('stop'):
                break
            exec(command['code'], globals())
            print(json.dumps({'state': state(), 'network': network[-8:], 'errors': errors[-5:]}, ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__ + ': ' + str(error).split('Call log:')[0], 'state': state() if not page.is_closed() else None}), flush=True)
    browser.close()
