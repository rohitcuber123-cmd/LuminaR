"""Immutable baseline for explicitly authorized local platform completion."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'


def main():
    target=ROOT/'reports/platform_completion_baseline.json'
    if target.exists():
        print('Existing platform completion baseline preserved.');return
    paths=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    hashes={}
    for name in paths:
        name=name.replace('\\','/');p=ROOT/name
        if not name.startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.cjs'} and p.stat().st_size<32*1024*1024:
            hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
            if name.startswith('frontend/src/') or name.startswith('backend/'):
                copy=ROOT/'.scratch/platform-completion/before'/name;copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(p.read_bytes())
    previous=json.loads((ROOT/'reports/full_product_browser_closure_baseline.json').read_text())
    artifacts={}
    for name in previous['artifact_metadata']:
        p=ROOT/name;s=p.stat();artifacts[name]={'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
    load_dotenv(ROOT/'.env')
    with MongoClient(os.getenv('MONGO_URI'),serverSelectionTimeoutMS=5000) as c:
        db=c['luminar_library'];q={'library_id':TEST}
        # Do not read or persist access-code hashes or other credential material.
        snapshots={name:list(db['institution_'+name].find(q,{'_id':0}).sort('library_id',1)) for name in ['libraries','memberships','library_books','holdings','lending_config','v2c_config']}
        snapshots['library_books'].sort(key=lambda x:x['library_book_id']);snapshots['holdings'].sort(key=lambda x:x['library_book_id'])
        authority=list(db.platform_role_assignments.find({}, {'_id':0}))
        count=db.books.estimated_document_count()
    value={'captured_at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,'TEST':snapshots,'global_count':count,'global_count_method':'estimated_document_count','artifact_metadata':artifacts,'existing_platform_assignments':authority,'approved_scope':'Dedicated local QA identity and explicit platform grant, disposable lifecycle library, Platform Libraries surface, shared context/cover repairs; no existing QA account elevation or TEST lifecycle mutation.'}
    target.write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
    print(json.dumps({'sources':len(hashes),'TEST_books':len(snapshots['library_books']),'TEST_holdings':len(snapshots['holdings']),'global_books':count,'artifacts':len(artifacts),'platform_assignments':len(authority)}))


if __name__=='__main__':main()
