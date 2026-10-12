"""Part 2F local QA through normal APIs and Chromium; credentials stay in memory."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
prefix = (ROOT / 'scripts/institution_v2d_browser_session.py').read_text(encoding='utf8').split('private_code=')[0]
exec(prefix.replace('v2d', 'v2f').replace('Part 2D', 'Part 2F'), globals())
import fitz
import time

private_code = secrets.token_urlsafe(20)
for letter, owner, private in [('A', 'owner', True), ('B', 'mixed', False), ('C', 'owner', False)]:
    value = {'name': 'Part 2F QA Library ' + letter, 'slug': f'part2f-{letter.lower()}-{suffix}', 'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY', 'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC'}
    if private:
        value['access_code'] = private_code
    fixtures[letter] = api('/libraries/register', 'POST', value, owner, 201)['library']['library_id']
for account in ['mixed', 'borrower']:
    api(f'/libraries/{fixtures["A"]}/join', 'POST', {'access_code': private_code}, account)
for letter in ['B', 'C']:
    api(f'/libraries/{fixtures[letter]}/join', 'POST', {}, 'borrower')
invite = api(f'/libraries/{fixtures["C"]}/invitations', 'POST', {'email': accounts['mixed']['email'], 'role': 'LIBRARIAN'}, expected=201)
api('/invitations/' + invite['invitation']['invitation_id'] + '/accept', 'POST', {'token': invite['invite_token']}, 'mixed')
for letter, owner in [('A', 'owner'), ('B', 'mixed'), ('C', 'owner')]:
    fixtures['books_' + letter] = []
    for number in range(2):
        fields = {'title': f'Part 2F {letter} resource book {number}', 'subjects': ['Community', 'Reference']}
        if number == 0:
            fields['global_work_id'] = 'OL19313623W'
        book = api(f'/libraries/{fixtures[letter]}/inventory/books', 'POST', cmd(**fields), owner, 201)
        fixtures['books_' + letter].append(book['library_book_id'])
proposal = migration.plan(db, {'platform_assignments': [{'user_id': accounts['platform']['user_id'], 'role': 'PLATFORM_ADMIN', 'approved': True, 'approved_by': 'local-development-review', 'approval_ref': 'USER-INSTITUTION-V2F-QA', 'reason': 'Disposable local asset lifecycle and Platform-without-membership checks; revoke at cleanup.'}]})
migration.apply(db, proposal)

fixture_dir = ROOT / '.scratch/institution-v2f/documents'
fixture_dir.mkdir(parents=True, exist_ok=True)
sample = fixture_dir / 'LuminaR Digital Resources QA.pdf'
pdf = fitz.open()
sheet = pdf.new_page()
sheet.insert_textbox(fitz.Rect(50, 50, 550, 740), '''LuminaR Digital Resources QA

This document is a safe local development fixture.
The Cedar Reading Room opens at 09:00 and closes at 18:00.
Readers may request two resource copies at a time.
The reference desk is on the second floor.
The annual reading workshop takes place in November.

Library digital assets have explicit ownership. A MEMBER resource is available only to active members of its exact library. A STAFF ONLY resource is available only to the active library administrator or librarian. Personal documents remain owned by their user session.
''', fontsize=12)
pdf.save(sample)
pdf.close()
base_credentials = credentials


def credentials(account):
    return (accounts[account]['email'], accounts[account]['password']) if account in accounts else base_credentials(account)


def refresh(account):
    email, password = credentials(account)
    response = requests.post('http://127.0.0.1:8002/auth/login', json={'email': email, 'password': password}, timeout=30)
    assert response.status_code == 200, 'QA login failed'
    auth_headers[account] = {'Authorization': 'Bearer ' + response.json()['access_token']}


def rag_api(path, method='GET', body=None, account='owner', expected=200):
    response = requests.request(method, 'http://127.0.0.1:8005' + path, json=body, headers=auth_headers[account], timeout=240)
    assert response.status_code == expected, f'{method} {path}: expected {expected}, got {response.status_code}'
    return response.json()


def shot(name):
    target = REPORTS / f'institution_v2f_{name}.png'
    page.screenshot(path=str(target), full_page=False, animations='disabled')
    return target.name


normal_login = login


def login(account):
    global context, page
    size = page.viewport_size or {'width': 1440, 'height': 900}
    context.close()
    context = browser.new_context(viewport=size)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: network.append({'path': urlparse(response.url).path, 'status': response.status}) if any(x in response.url for x in ['/api/', '/rag-api/', '/search-api/', '/recommendation-api/']) else None)
    return normal_login(account)


sys.stdout.reconfigure(encoding='utf8')
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    network = []
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    print(json.dumps({'browser': browser.version, 'fixtures': fixtures, 'QA_accounts': [{'email': row['email'], 'user_id': row['user_id']} for row in accounts.values()], 'mixed_roles': {'A': 'GENERAL_USER', 'B': 'ADMIN', 'C': 'LIBRARIAN'}}), flush=True)
    for line in sys.stdin:
        try:
            command = json.loads(line)
            if command.get('stop'):
                break
            exec(command['code'], globals())
            print(json.dumps({'state': state(), 'network': network[-10:], 'errors': errors[-5:]}, ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__ + ': ' + str(error).split('Call log:')[0], 'state': state() if not page.is_closed() else None}), flush=True)
    browser.close()
