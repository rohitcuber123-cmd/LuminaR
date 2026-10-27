"""Transcribe observed Chromium checks and reversibly retire owned QA data."""
import json
from datetime import datetime, timezone
from pathlib import Path

CHECKS = [
 ('GLOBAL','rating above 4',['Rating: > 4'],10,'EXECUTABLE','All ten displayed ratings >4'),
 ('GLOBAL','rating at least 4',['Rating: ≥ 4'],10,'EXECUTABLE','All ratings >=4; boundary4 displayed'),
 ('GLOBAL','rating below 4',['Rating: < 4'],10,'EXECUTABLE','All ten displayed ratings <4'),
 ('GLOBAL','rating at most 4',['Rating: ≤ 4'],10,'EXECUTABLE','All ratings <=4; boundary4 displayed'),
 ('GLOBAL','rating at least 4.5 but below 4.5',['Rating: ≥ 4.5','Rating: < 4.5'],0,'CONTRADICTORY','Conflict decision; Edit your search to continue'),
 ('GLOBAL','rating above 4 and at most 4',['Rating: > 4','Rating: ≤ 4'],0,'CONTRADICTORY','Conflict decision; Edit your search to continue'),
 ('GLOBAL','rating at least 4 and at most 4',['Rating: ≥ 4','Rating: ≤ 4'],10,'EXECUTABLE','All ten displayed ratings exactly4; no blocked decision'),
 ('GLOBAL','books titled "1984"',['Title / Author: 1984'],10,'EXECUTABLE','1984 title results; no year/rating chip'),
 ('GLOBAL','books about Python 3',['Topic: python 3'],7,'EXECUTABLE','Python3 results; no rating/year chip'),
 ('GLOBAL','books by Terry Pratchett about witches',['Topic: witches','Author: terry pratchett'],1,'EXECUTABLE','Equal Rites / Wyrd Sisters / Witches Abroad by Terry Pratchett'),
 ('GLOBAL','rating above',[],0,'INCOMPLETE','Rating-value clarification; unfinished decision; Edit your search to continue'),
 ('GLOBAL','books under 250 pages',[],0,'UNSUPPORTED','Scope cannot enforce strict field; remove page-count choice; no cards'),
 ('PRIVATE_PATRON','Fiction not Romance',['Genre / Subject: Fiction','Exclude subject: Romance'],2,'EXECUTABLE','Wizards Fiction4.5 and Mystery Fiction5; canonical exclusion only'),
 ('PRIVATE_PATRON','include Fiction but exclude Fiction',['Genre / Subject: Fiction','Exclude subject: Fiction'],0,'CONTRADICTORY','Same canonical subject conflict; no cards'),
 ('PRIVATE_PATRON','online-only and physical-only',['Format: Online','Format: Physical'],0,'CONTRADICTORY','Exclusive format conflict; no cards'),
 ('PRIVATE_PATRON','online and physical',['Format: Physical + Online'],0,'EXECUTABLE','No books match all selected filters.; valid execution, no blocked-decision panel; all fixture books physical only'),
 ('PUBLIC_PATRON','rating above 4.5',['Rating: > 4.5'],3,'EXECUTABLE','All three displayed ratings5'),
 ('PRIVATE_OUTSIDER','open private catalogue',[],0,'ACCESS_DENIED','Unable to open this library / Library resource not found.; no private title, vocabulary or search controls'),
]

def main():
    from backend.database.mongodb import db
    path = Path('reports/search_v2c_c4_fixture.json')
    f = json.loads(path.read_text())
    assert db.name == 'luminar_library' and f['qa_owned']
    assert db.institution_libraries.find_one({'library_id':f['library_id'],'name':'V2CCR Clause QA'})
    ids = [f['member_id'],f['outsider_id']]
    for uid in ids:
        user = db.users.find_one({'user_id':uid})
        assert user['name'].startswith('V2CCR Browser ')
        db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
    db.institution_memberships.update_many({'user_id':{'$in':ids}},{'$set':{'status':'REMOVED'}})
    db.institution_libraries.update_one({'library_id':f['library_id']},{'$set':{'status':'ARCHIVED'}})
    assert all(not db.users.find_one({'user_id':uid})['is_active'] for uid in ids)
    assert db.institution_libraries.find_one({'library_id':f['library_id']})['status'] == 'ARCHIVED'
    f['status'] = 'CLEANED_REVERSIBLY: owned QA accounts disabled; memberships removed; private QA library archived; residual sessions follow normal TTL'
    path.write_text(json.dumps(f,indent=2)+'\n')
    out = {'status':'PASS','observed_at':datetime.now(timezone.utc).isoformat(),
        'browser':'Real Chromium IAB on localhost5173; fresh Search8003 process44056 started after C4 freeze',
        'cases':[{'scope':s,'query':q,'chips':chips,'rendered_article_cards':count,'typed_decision':decision,'observed':observed,'status':'PASS'} for s,q,chips,count,decision,observed in CHECKS],
        'private_leaks_observed':0,'reversible_cleanup_verified':True,'fixtures':str(path),
        'screenshot':'Neutral outsider denial captured in conversation browser-tool evidence; no standalone image file claimed',
        'credentials':'Retained only in local credentials file for disabled disposable QA accounts; not copied to reports',
        'source_freeze':'search_v2c_c4_freeze.json','loading_snapshots':'Transient snapshots discarded; final settled chips and decisions recorded.',
        'limitations':'Focused checks of actual execution and chips; browser alone does not establish full development acceptance.'}
    Path('reports/search_v2c_c4_browser.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    print('18/18 focused Chromium checks PASS; owned QA fixtures retired reversibly')

if __name__ == '__main__':
    main()
