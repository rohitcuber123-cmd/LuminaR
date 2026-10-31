import hashlib,json
from scripts.institution_v2o_migration_preflight import validate


def test_false_strings_do_not_qualify_preflight():
    result=validate({'minimum_roles_reviewed':'false','service_identity_DPAPI_verified':'true',
                     'cross_store_restore_approved':'false','write_freeze_confirmed':'false'})
    assert all(k in result['errors'] for k in ['MINIMUM_ROLE_REVIEW_REQUIRED','SERVICE_SECRET_PROFILE_REQUIRED','APPROVED_CROSS_STORE_RESTORE_REQUIRED','WRITE_FREEZE_REQUIRED'])
    assert not result['executed_cutover']


def test_production_manifest_rejects_fixture_restore_evidence(tmp_path):
    proof=tmp_path/'fixture.json';proof.write_text(json.dumps({'result':'FIXTURE_PASS'}))
    result=validate({'deployment_class':'PRODUCTION','database':'approved_database',
                     'restore_evidence_path':str(proof),'restore_evidence_sha256':hashlib.sha256(proof.read_bytes()).hexdigest()})
    assert 'PRODUCTION_RESTORE_CANNOT_USE_FIXTURE_PROOF' in result['errors']
