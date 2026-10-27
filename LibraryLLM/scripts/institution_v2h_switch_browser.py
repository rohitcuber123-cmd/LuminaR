"""Resume the polling switch check using the already queued safe retry."""
import sys,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
fault_source=(ROOT/'scripts/institution_v2h_failure_browser.py').read_text(encoding='utf8')
exec(fault_source.split('with sync_playwright() as p:')[0],globals())
failure_rows={r['event']:r for r in db.institution_audit.find({'library_id':fixture})}
failed={'state':'FAILED','evidence':'Previously captured real failed UI and audit','event':failure_rows.get('SEARCH_INDEX_BUILD_FAILED',{}).get('event')}
recovery={'state':'RECOVERY_REQUIRED','evidence':'Previously captured unknown outcome UI','event':failure_rows.get('SEARCH_INDEX_BUILD_RECOVERY_REQUIRED',{}).get('event')}
recovered={'state':'FAILED','evidence':'Explicit Part 2G operator recovery completed before safe retry'}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'));ready(page,fixture)
    exec(textwrap.dedent('    held={}'+fault_source.split('    held={}',1)[1]),globals())

