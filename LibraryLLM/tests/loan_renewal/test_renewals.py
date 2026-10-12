from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from conftest import NOW, http
from backend.services import notification_service as ns, issue_service as loans, loan_renewal_service as renewals
from backend.services.loan_notification_service import reconcile_loan_notifications


def loan(db, delta=2, uid=2, iid=1, **extra):
    doc={'issue_id':iid,'user_id':uid,'work_id':'OL1W','book_id':1,'title':'Dracula',
         'issued_at':NOW-timedelta(days=12),'due_date':NOW+timedelta(days=delta),
         'status':'ISSUED','returned_at':None,'fine_amount':0,**extra}
    db.issues.insert_one(doc);doc.pop('_id',None);return doc


def body(doc, rid=None):return {'request_id':str(rid or uuid4()),'expected_due_date':ns.utc(doc['due_date']).isoformat()}
def post(doc, uid=2, payload=None):return http(uid).post(f"/issues/{doc['issue_id']}/renew",json=payload or body(doc))


@pytest.mark.parametrize('uid', [1,2,3,4])
@pytest.mark.parametrize('status', ['ISSUED','RETURNED'])
def test_every_legacy_renewal_is_read_only(isolated, uid, status):
    doc=loan(isolated,status=status); before=list(isolated.issues.find({}))
    assert post(doc,uid).status_code == 410
    assert list(isolated.issues.find({})) == before
    assert isolated.activity.count_documents({}) == 0


def test_racing_legacy_renewals_have_no_writer(isolated):
    doc=loan(isolated); before=list(isolated.issues.find({}))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:post(doc).status_code,range(4)))
    assert results == [410]*4 and list(isolated.issues.find({})) == before


def test_own_historical_eligibility_is_explicitly_read_only(isolated):
    loan(isolated)
    result=http(2).get('/issues/1/renewal')
    assert result.status_code == 200
    assert result.json()['renewal']['eligible'] is False
    assert result.json()['renewal']['reason'] == 'LEGACY_READ_ONLY'
    assert http(3).get('/issues/1/renewal').status_code == 403


@pytest.mark.parametrize('key,value',[('LOAN_RENEWAL_DAYS','bad'),('LOAN_MAX_RENEWALS','21')])
def test_shared_canonical_policy_rejects_invalid_configuration(monkeypatch,key,value):
    monkeypatch.setenv(key,value)
    with pytest.raises(renewals.RenewalError): renewals.policy()


def test_shared_canonical_policy_honors_configuration(monkeypatch):
    monkeypatch.setenv('LOAN_RENEWAL_DAYS','7');monkeypatch.setenv('LOAN_MAX_RENEWALS','2')
    assert renewals.policy()['days']==7 and renewals.policy()['max_renewals']==2
