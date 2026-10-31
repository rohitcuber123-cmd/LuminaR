"""Existing UI assertions against owned JSX fixtures, without product edits."""
import json
from pathlib import Path
import re
import subprocess
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
FRONT=ROOT/'frontend';OUT=ROOT/'reports'


def main():
    # Preserve failed harness setup evidence before an explicitly corrected run.
    import shutil
    for old in OUT.glob('institution_v2o3_jsx_*.log'):
        initial=old.with_name(old.stem+'_initial.log')
        if not initial.exists() and '_initial' not in old.stem:shutil.copyfile(old,initial)
        if '_initial' not in old.stem and 'React is not defined' in old.read_text(encoding='utf8'):
            shutil.copyfile(old,old.with_name(old.stem+'_transform_error.log'))
    scope=FRONT/'.scratch/institution-v2o3'/uuid4().hex
    assert scope.resolve().is_relative_to((FRONT/'.scratch/institution-v2o3').resolve())
    # Extra UUID directory adds one level; all imports still resolve to real,
    # unchanged product dependencies in frontend/src and frontend/node_modules.
    source="import React from 'react'\n"+(FRONT/'src/pages/LibraryIntelligence.tsx').read_text().replace("from '../","from '../../../../src/")
    test=(FRONT/'tests/institution-intelligence-controls.test.tsx').read_text()
    test=test.replace("import('../src/pages/LibraryIntelligence')","import('../pages/LibraryIntelligence')").replace("import('../src/","import('../../../../src/")
    fixtures={
        'reviewed_original':source,
        'passive_layout':source.replace('<section className=','<article className=').replace('</section>','</article>'),
        'button_tag':source.replace('<button disabled={busy || empty} onClick={onBuild}>','<span disabled={busy || empty} onClick={onBuild}>').replace('{actionLabel(target)}</button>','{actionLabel(target)}</span>'),
        'build_hover':source.replace('onClick={onBuild}','onMouseEnter={onBuild}'),
        'progress_tag':source.replace('<progress id=','<div id=')}
    rows=[]
    for label,page in fixtures.items():
        # Use a fixed page path per isolated process, avoiding module aliases.
        (scope/'pages').mkdir(parents=True,exist_ok=True);(scope/'tests').mkdir(parents=True,exist_ok=True)
        (scope/'pages/LibraryIntelligence.tsx').write_text(page)
        (scope/'pages/LibraryIntelligence.css').write_text('')
        target=scope/'tests/existing-controls.test.tsx';target.write_text(test)
        log=OUT/f'institution_v2o3_jsx_{label}.log'
        with log.open('w',encoding='utf8') as out:
            p=subprocess.run(['node',str(FRONT/'node_modules/tsx/dist/cli.mjs'),'--tsconfig','tsconfig.app.json','--test',
                '--test-name-pattern=test_admin_build_search_button|test_intelligence_dialog_escape_and_restore|test_search_progress',str(target)],
                cwd=FRONT,stdout=out,stderr=subprocess.STDOUT,timeout=90)
        text=log.read_text(encoding='utf8')
        count=lambda key:sum(map(int,re.findall(r'^. '+key+r' (\d+)\s*$',text,re.M)))
        expected=label not in {'reviewed_original','passive_layout'}
        setup_error=any(s in text for s in ('ReferenceError','Cannot find module','ERR_MODULE_NOT_FOUND'))
        rows.append({'scenario':label,'exit':p.returncode,'passed':count('pass'),'failed':count('fail'),'skipped':count('skipped'),
            'expected_behavior_test_failure':expected,'expectation_met':p.returncode!=0 and count('fail')>0 and not setup_error if expected else p.returncode==0 and count('pass')==3,
            'log':log.name,'fixture':str(scope.relative_to(ROOT)),
            'test_source':'Exact existing assertions; relative imports redirected to owned page copy. Fixture-only React import supports classic JSX transform outside app src. Three selected accessibility/build/progress checks.'})
        print(json.dumps(rows[-1]),flush=True)
    (OUT/'institution_v2o3_jsx_behavior.json').write_text(json.dumps({'status':'PASS' if all(r['expectation_met'] for r in rows) else 'FAIL','rows':rows,
        'actual_product_source_modified':False,'limits':'Focused JSDOM role/focus/event/progress assertions; no fresh Chromium or broad accessibility proof.'},indent=2))
    return not all(r['expectation_met'] for r in rows)


if __name__=='__main__':raise SystemExit(main())
