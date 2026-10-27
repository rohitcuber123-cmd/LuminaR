"""Transcribe verified Chromium UI observations; reversible QA cleanup only."""
from pathlib import Path
import json

checks=[
('GLOBAL','rating no less than 4.5','Rating: >= 4.5'),
('GLOBAL','rating above 4','Rating: > 4'),
('GLOBAL','rating at least 4.5 but below 4.5','CONTRADICTORY; two bounds, conflict message and blocked results'),
('GLOBAL','books by Terry Pratchett about witches','Author: terry pratchett; Topic: witches; matching author results'),
('GLOBAL','books about "Python 3"','Topic: Python 3; no rating/year chip'),
('GLOBAL','rating above','INCOMPLETE; unfinished message and genuine value clarification'),
('GLOBAL','rating above -> genuine value4.2','Rating: > 4.2; clarification closed'),
('GLOBAL','remove rating chip','Rating chip removed'),
('GLOBAL','books under 250 pages','UNSUPPORTED; no results; remove-page-count choice'),
('PUBLIC_PATRON','rating above 4.5','Rating: > 4.5'),
('PRIVATE_PATRON','rating no more than 4.5','Rating: <= 4.5'),
('PRIVATE_PATRON','neur','Scoped Neural Networks subject suggestion; selected successfully'),
('PRIVATE_PATRON','detectve fiction -> Keep original wording','Correction offered; keep-original returns Topic: detectve fiction with no forced subject'),
('PRIVATE_OUTSIDER','open private catalogue','Unable to open this library / Library resource not found; no private titles or search controls')]

def main():
    Path('reports/search_v2c_c2_browser.json').write_text(json.dumps({
        'status':'PASS','browser':'Real Chromium in-app browser, UI-driven localhost5173; restarted Search API8003',
        'not_final_V2C_C_acceptance':True,'cases':[{'scope':s,'query':q,'observed':o,'status':'PASS'} for s,q,o in checks],
        'session_preservation':'search_v2c_c2_browser_before_resolution.json: accepted version4 Python3 survives incomplete query; genuine clarification later applied and rating chip removed.',
        'private_leaks_observed':0,'fixture':'search_v2c_c2_fixture.json',
        'screenshot':'Neutral outsider denial screenshot captured in conversation tool evidence.',
        'timing_note':'Browser bridge waitFor deadlines occurred while final DOM showed expected chip/status; outcomes reobserved before proceeding.',
        'cleanup_policy':'Combined cleanup command was rejected by automatic approval review. Credential file retained. Use reversible account disable/library archive, no destructive file removal.'},indent=2))
    from backend.database.mongodb import db
    path=Path('reports/search_v2c_c2_fixture.json');fixture=json.loads(path.read_text())
    assert fixture['qa_owned'] and db.name=='luminar_library'
    assert db.institution_libraries.find_one({'library_id':fixture['library_id'],'name':'V2CCR Clause QA'})
    ids=[fixture['member_id'],fixture['outsider_id']]
    for uid in ids:
        user=db.users.find_one({'user_id':uid});assert user['name'].startswith('V2CCR Browser ')
        db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
    db.institution_memberships.update_many({'user_id':{'$in':ids}},{'$set':{'status':'REMOVED'}})
    db.institution_libraries.update_one({'library_id':fixture['library_id']},{'$set':{'status':'ARCHIVED'}})
    fixture['status']='CLEANED_REVERSIBLY: disposable accounts disabled; memberships removed; private QA library archived; residual sessions follow normal TTL'
    fixture['temporary_credentials_file_retained_after_approval_rejection']=True
    path.write_text(json.dumps(fixture,indent=2))
    assert all(not db.users.find_one({'user_id':uid})['is_active'] for uid in ids)
    print(json.dumps({'browser':'PASS','reversible_QA_cleanup':'VERIFIED','credential_file':'retained for disabled disposable accounts'}))

if __name__=='__main__':main()
