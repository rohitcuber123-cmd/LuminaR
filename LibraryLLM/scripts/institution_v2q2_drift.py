"""Non-invasive live metadata comparison. Persist hashed identities only."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from dotenv import dotenv_values
from pymongo import MongoClient
from scripts.institution_v2i_baseline import digest

def main():
 cfg=dotenv_values(R/'.env');old=json.loads((R/'reports/institution_v2q1d_preservation_drift.json').read_text())
 fixture=json.loads((R/'reports/institution_v2q2_fixture_manifest.json').read_text())
 owned={x['library_id'] for x in fixture['libraries']}
 extra=R/'reports/institution_v2q2_recommendation_matrix.json'
 if extra.exists():owned.update(x['library_id'] for x in json.loads(extra.read_text()).get('owned_additional_libraries',[]))
 hashed=lambda x:hashlib.sha256(str(x).encode()).hexdigest()[:16]
 with MongoClient(cfg['MONGO_URI'],serverSelectionTimeoutMS=5000) as client:
  db=client[cfg.get('MONGO_DB_NAME') or 'luminar_library'];assert db.name=='luminar_library'
  latest=[];latest_scope=None
  for event in db.institution_audit.find({}).sort('created_at',-1).limit(8):
   # Inspect only stable event-kind names, timestamps and pseudonymous scope.
   kind=event.get('action') or event.get('event_type') or event.get('event') or event.get('operation')
   latest.append({'timestamp':str(event.get('created_at') or event.get('timestamp')),'event_kind':kind if isinstance(kind,str) and len(kind)<100 else None,'library_hash':hashed(event.get('library_id')),'is_current_owned_fixture':str(event.get('library_id')) in owned})
   if latest_scope is None:latest_scope=event.get('library_id')
  current={n:{'count':db[n].count_documents({}),'sha256':digest(db[n].find({}))} for n in ['institution_audit','institution_memberships','institution_security']}
  matches={n:db[n].count_documents({'library_id':{'$in':list(owned)}}) for n in ['institutions','institution_memberships','institution_audit','institution_security']}
  related_members=[{'joined_at':str(x.get('joined_at')),'updated_at':str(x.get('updated_at')),'status':x.get('status')} for x in db.institution_memberships.find({'library_id':latest_scope},{'_id':0,'joined_at':1,'updated_at':1,'status':1})]
  prior_matches=[]
  for p in (R/'reports').glob('institution_v2q1*'):
   if p.suffix in {'.json','.md'} and p.stat().st_size<8_000_000 and latest_scope and str(latest_scope) in p.read_text(encoding='utf8',errors='replace'):
    prior_matches.append(p.name)
 data={'captured_at':datetime.now(timezone.utc).isoformat(),'previous_drift_retained':old,'current':current,'latest_sanitized_audit':latest,'current_fixture_matches_in_live_db':matches,
       'attribution':'UNATTRIBUTED','assessment':'No actor attribution inferred from timestamps or library hashes. No raw personal identifiers, user records or private content exported. No live rollback/rebaseline.',
       'correlation_limits':'Prior evidence has collection digests, counts and scope hashes, not historical membership row snapshots or request IDs. Running service timestamps cannot identify the initiator of a membership/security change.',
       'related_membership_times_only':related_members,'prior_reports_referencing_latest_scope':prior_matches,
       'event_sequence_assessment':'Three failed private joins, an access-code change and a successful private join correlate with the five audit additions, security digest change and membership increment. This identifies an event sequence, not who initiated or authorized it.'}
 (R/'reports/institution_v2q2_metadata_drift.json').write_text(json.dumps(data,indent=2,default=str))
 print(json.dumps({'attribution':data['attribution'],'counts':{n:x['count'] for n,x in current.items()},'fixture_matches':matches}))

if __name__=='__main__':main()
