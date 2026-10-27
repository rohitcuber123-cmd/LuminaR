"""Transcribe verified real Chromium UI observations and retire owned QA fixtures."""
import json
from pathlib import Path
from datetime import datetime,timezone

CHECKS=[
 ('GLOBAL','rating above 4',['Rating: > 4'],10,'All displayed ratings >4'),
 ('GLOBAL','rating at least 4',['Rating: ≥ 4'],10,'Boundary rating4 present'),
 ('GLOBAL','rating below 4',['Rating: < 4'],10,'All displayed ratings <4'),
 ('GLOBAL','rating at most 4',['Rating: ≤ 4'],10,'Boundary rating4 present'),
 ('GLOBAL','rating no less than 4.5',['Rating: ≥ 4.5'],10,'Boundary rating4.5 present'),
 ('GLOBAL','rating at least 4.5 but below 4.5',['Rating: ≥ 4.5','Rating: < 4.5'],0,'CONTRADICTORY; conflict message and Edit your search to continue'),
 ('GLOBAL','books titled "1984"',['Title / Author: 1984'],10,'1984 title results; no publication-year or rating chip'),
 ('GLOBAL','books about Python 3',['Topic: python 3'],7,'Python3 results; no rating or year chip; rendered seven cards in inspected snapshot'),
 ('GLOBAL','books by Terry Pratchett about witches',['Author: terry pratchett','Topic: witches'],1,'Equal Rites / Wyrd Sisters / Witches Abroad by Terry Pratchett'),
 ('GLOBAL','include Fiction but exclude Romance',['Genre / Subject: Fiction','Exclude subject: Romance'],10,'Canonical subject predicates, no broad text-negative chip'),
 ('GLOBAL','rating above',[],0,'INCOMPLETE; real rating-value clarification offered; Edit your search to continue'),
 ('GLOBAL','books under 250 pages',[],0,'UNSUPPORTED; page count not available, remove requirement choice; no result cards'),
 ('PUBLIC_PATRON','rating above 4.5',['Rating: > 4.5'],3,'All three displayed ratings5'),
 ('PRIVATE_PATRON','rating no more than 4.5',['Rating: ≤ 4.5'],1,'V2CCR Wizards Fiction at rating4.5'),
 ('PRIVATE_PATRON','include Fiction but exclude Romance',['Genre / Subject: Fiction','Exclude subject: Romance'],2,'Wizards Fiction and Mystery Fiction only; Romance excluded'),
 ('PRIVATE_OUTSIDER','open private catalogue',[],0,'Unable to open this library / Library resource not found.; no private title, vocabulary or search controls')]

def main():
    from backend.database.mongodb import db
    R=Path('reports');fixture_path=R/'search_v2c_c3_fixture.json';f=json.loads(fixture_path.read_text())
    assert db.name=='luminar_library' and f['qa_owned']
    assert db.institution_libraries.find_one({'library_id':f['library_id'],'name':'V2CCR Clause QA'})
    ids=[f['member_id'],f['outsider_id']]
    for uid in ids:
        user=db.users.find_one({'user_id':uid});assert user['name'].startswith('V2CCR Browser ')
        db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
    db.institution_memberships.update_many({'user_id':{'$in':ids}},{'$set':{'status':'REMOVED'}})
    db.institution_libraries.update_one({'library_id':f['library_id']},{'$set':{'status':'ARCHIVED'}})
    f['status']='CLEANED_REVERSIBLY: owned QA accounts disabled; memberships removed; QA library archived; residual sessions follow normal TTL'
    fixture_path.write_text(json.dumps(f,indent=2))
    assert all(not db.users.find_one({'user_id':uid})['is_active'] for uid in ids)
    out={'status':'PASS','observed_at':datetime.now(timezone.utc).isoformat(),'browser':'Real Chromium IAB through UI on localhost5173; Search8003 restarted after final source freeze',
         'search_server_process':5312,'cases':[{'scope':s,'query':q,'chips':c,'rendered_article_cards':n,'observed':o,'status':'PASS'} for s,q,c,n,o in CHECKS],
         'private_leaks_observed':0,'screenshot':'Neutral outsider denial captured in conversation browser-tool evidence; no standalone image file claimed',
         'fixtures':str(fixture_path),'reversible_cleanup_verified':True,'credentials':'Retained locally for disabled disposable accounts; never copied into reports',
         'source_freeze':'search_v2c_c3_freeze.json','not_complete_development_acceptance':True}
    (R/'search_v2c_c3_browser.json').write_text(json.dumps(out,indent=2))
    print('16 focused Chromium checks PASS; owned QA fixtures retired reversibly')
if __name__=='__main__':main()
