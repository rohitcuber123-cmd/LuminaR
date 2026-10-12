"""Real Chromium review session. Credentials are read only at runtime, never logged.

The stdin console is for explicit developer-directed Playwright review actions.
No authentication state or screenshots of credential fields are persisted.
"""
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('LUMINAR_BROWSER_REVIEW_URL', 'http://127.0.0.1:5173')
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
REPORTS = ROOT / 'reports'

def credentials(account):
    if account == 'platform':
        return os.environ['LUMINAR_BROWSER_PLATFORM_EMAIL'], os.environ['LUMINAR_BROWSER_PLATFORM_PASSWORD']
    prompt = Path(os.getenv('LUMINAR_BROWSER_QA_PROMPT', r'C:\Users\balak\.codex\attachments\8bb75c31-5c9d-4f5f-bf53-7b8a765af2f5\Pasted text.txt')).read_text(encoding='utf-8-sig')
    email = 'karthikeya.ixa.10@gmail.com' if account == 'patron' else 'rohitcuber123@gmail.com'
    tail = prompt.split(email,1)[1].lstrip()
    password = tail.splitlines()[0].strip()
    password = re.sub(r'(?i)^password\s*[:=]\s*', '', password)
    return email, password

def state():
    return page.evaluate("""() => ({route:location.pathname+location.search+location.hash, title:document.title, headings:[...document.querySelectorAll('h1,h2,h3')].map(e=>e.textContent.trim()).slice(0,40), links:[...document.querySelectorAll('a[href]')].map(e=>({text:(e.textContent||e.getAttribute('aria-label')||'').trim().slice(0,80),href:e.getAttribute('href')})).slice(0,90), buttons:[...document.querySelectorAll('button')].map(e=>({text:(e.textContent||e.getAttribute('aria-label')||'').trim().slice(0,90),disabled:e.disabled})).slice(0,80), inputs:[...document.querySelectorAll('input,select,textarea')].map(e=>({tag:e.tagName,type:e.type,placeholder:e.placeholder||'',label:e.id||e.getAttribute('aria-label')})), alerts:[...document.querySelectorAll('[role=alert]')].map(e=>e.textContent.trim()),width:innerWidth,scrollWidth:document.documentElement.scrollWidth})""")

def goto(path):
    page.goto(BASE+path,wait_until='domcontentloaded',timeout=90000)

def login(account):
    goto('/login')
    email, password = credentials(account)
    page.locator('input[type=email]').fill(email)
    page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click()
    page.wait_for_url(lambda u:'/login' not in str(u),timeout=45000)
    page.locator('#main-content').wait_for(timeout=45000)
    return {'account':account,'route':urlparse(page.url).path,'authenticated':True}

def shot(name):
    target=REPORTS/f'full_product_browser_{name}.png'
    page.screenshot(path=str(target),full_page=True,animations='disabled')
    return str(target)

def put(name,value):
    (REPORTS/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf8')
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':900})
        page=context.new_page()
        network=[]
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('response',lambda response:network.append({'path':urlparse(response.url).path,'status':response.status}) if any(x in response.url for x in ['/api/','/search-api/','/recommendation-api/','/rag-api/']) else None)
        print(json.dumps({'browser':'Chromium','version':browser.version,'runtime':BASE}),flush=True)
        if os.getenv('LUMINAR_BROWSER_BATCH_SCRIPT'):
            exec(Path(os.environ['LUMINAR_BROWSER_BATCH_SCRIPT']).read_text(encoding='utf8'),globals())
        for line in sys.stdin:
            try:
                command=json.loads(line)
                if command.get('stop'):break
                exec(command['code'],globals())
                print(json.dumps({'state':state(),'network':network[-12:],'errors':errors[-5:]},ensure_ascii=False),flush=True)
            except Exception as error:
                print(json.dumps({'error':type(error).__name__+': '+str(error).split('Call log:')[0],'state':state() if not page.is_closed() else None},ensure_ascii=False),flush=True)
        browser.close()
