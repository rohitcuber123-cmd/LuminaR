"""Executable review-manifest validation only; never performs live cutover actions."""
import argparse,hashlib,json
from pathlib import Path


def validate(plan):
    errors=[]
    for key in ['installation_owner','dba_owner','application_owner','windows_secret_owner','backup_owner','incident_owner','maintenance_window','approval_reference']:
        if not isinstance(plan.get(key),str) or not plan[key].strip() or plan[key] in {'UNKNOWN','PENDING'}:errors.append(key+'_REQUIRED')
    if plan.get('deployment_class') not in {'DEVELOPMENT','STAGING','PRODUCTION'}:errors.append('CLASSIFICATION_REQUIRED')
    if plan.get('mongo_version')!='8.3.4':errors.append('REHEARSED_VERSION_REVIEW_REQUIRED')
    if plan.get('minimum_roles_reviewed') is not True:errors.append('MINIMUM_ROLE_REVIEW_REQUIRED')
    if plan.get('service_identity_DPAPI_verified') is not True:errors.append('SERVICE_SECRET_PROFILE_REQUIRED')
    if plan.get('cross_store_restore_approved') is not True:errors.append('APPROVED_CROSS_STORE_RESTORE_REQUIRED')
    if plan.get('write_freeze_confirmed') is not True:errors.append('WRITE_FREEZE_REQUIRED')
    proof=Path(plan.get('restore_evidence_path','__missing__'))
    if not proof.is_file() or hashlib.sha256(proof.read_bytes()).hexdigest()!=plan.get('restore_evidence_sha256'):errors.append('RESTORE_EVIDENCE_HASH_REQUIRED')
    if plan.get('deployment_class')=='PRODUCTION' and proof.is_file():
        try:evidence=json.loads(proof.read_text())
        except (ValueError,OSError):evidence={}
        if (evidence.get('kind')!='AUTHORIZED_PRODUCTION_RESTORE' or not evidence.get('approved_by')
                or not evidence.get('checkpoint_id') or not plan.get('database') or evidence.get('database')!=plan['database']):
            errors.append('PRODUCTION_RESTORE_CANNOT_USE_FIXTURE_PROOF')
    return {'ready_for_operator_review':not errors,'errors':errors,'executed_cutover':False,'created_credentials':False,'changed_auth_or_ACL':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest',type=Path);args=parser.parse_args()
    print(json.dumps(validate(json.loads(args.manifest.read_text())),indent=2))
