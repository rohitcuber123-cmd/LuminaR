from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4
import pytest
from scripts.institution_v2d_migration import decision
from backend.services import institution_repository as repo, tenant_notification_service as tn, notification_service as ns
from test_events_notifications import request, issue, dispatch


@pytest.mark.parametrize('kind',['event','notification'])
def test_migration_never_infers_tenant_from_work_or_membership(kind):
    field='event_id' if kind=='event' else 'notification_id'
    row={field:str(uuid4()),'library_id':'LIB001','work_id':'OL1W','user_id':1}
    patch,classification=decision(row,kind,{},lambda _:True)
    assert patch is None and classification=='AMBIGUOUS_'+kind.upper()+'_TENANCY'


@pytest.mark.parametrize('kind',['event','notification'])
def test_migration_explicit_mapping_and_approval(kind):
    field='event_id' if kind=='event' else 'notification_id';identity=str(uuid4());library=str(uuid4())
    row={field:identity,'library_id':'legacy-a'}
    plan={'records':{identity:{'scope':'LIBRARY','approved':True,'approved_by':'reviewer','reason':'Verified canonical ownership.'}},'library_map':{'legacy-a':library}}
    patch,classification=decision(row,kind,plan,lambda value:value==library)
    assert patch['library_id']==library and classification=='LIBRARY_RESOLVABLE'
    plan['records'][identity]['approved']=False
    assert decision(row,kind,plan,lambda _:True)[0] is None


def test_migration_does_not_overwrite_tenant_with_global():
    identity=str(uuid4());row={'event_id':identity,'library_id':'legacy-a'}
    plan={'records':{identity:{'scope':'GLOBAL','approved':True,'approved_by':'reviewer','reason':'Wrong global proposal.'}}}
    assert decision(row,'event',plan,lambda _:True)[0] is None


def test_event_reads_wait_for_summary_gate(client,setup):
    entered=Event();release=Event()
    def summary():
        with repo.library_mutation(setup[0]):entered.set();release.wait(5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner=pool.submit(summary);assert entered.wait(5)
        read=pool.submit(lambda:client.get(f'/libraries/{setup[0]}/staff/events'))
        assert not read.done();release.set();owner.result()
        assert read.result().status_code==200


def test_outbox_same_plan_and_committed_receipt(client,setup,database):
    row=request(client,setup)
    operation=database.institution_lending_operations.find_one({'operation_id':row['operation_id']})
    intents=[step for step in operation['effects'] if step['collection']=='notification_outbox']
    assert len(intents)==2 and all(step['query']['library_id']==setup[0] for step in intents)
    assert all(step['values']['operation_id']==operation['operation_id'] for step in intents)


def test_notice_ack_loss_retries_without_duplicate(client,setup,database,monkeypatch):
    issue(client,setup);original=ns.insert_notice
    def after_write(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('Injected lost acknowledgement after inbox write.')
    monkeypatch.setattr(ns,'insert_notice',after_write)
    assert tn.materialize()['failed']==3 and database.notifications.count_documents({})==3
    monkeypatch.setattr(ns,'insert_notice',original)
    assert tn.materialize(stamp=repo.now()+timedelta(hours=1))['delivered']==3
    assert database.notifications.count_documents({})==3
