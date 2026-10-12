"""Explicit review-only scope migration. Default dry run; local apply only.

No work/title/membership inference. A per-record approved decision plus explicit
legacy-to-UUID mapping is required. Existing identity and payload are preserved.
"""
import argparse
import json
import os
from pathlib import Path
from uuid import UUID
from urllib.parse import urlparse
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.write_concern import WriteConcern

ROOT=Path(__file__).resolve().parents[1]


def decision(row,kind,plan,library_exists):
    field='event_id' if kind=='event' else 'notification_id'
    identity=row.get(field)
    try:UUID(identity)
    except (ValueError,TypeError,AttributeError):return None,'UNKNOWN_REVIEW_REQUIRED'
    old_scope=row.get('scope');old_library=row.get('library_id')
    if old_scope in ['GLOBAL','PLATFORM'] and not old_library:return None,'GLOBAL' if kind=='notification' else 'GLOBAL_PLATFORM'
    if old_scope=='LIBRARY':
        try:library_id=str(UUID(old_library))
        except (ValueError,TypeError,AttributeError):return None,'AMBIGUOUS_'+kind.upper()+'_TENANCY'
        if library_exists(library_id):return None,'LIBRARY_TENANT'
    reviewed=plan.get('records',{}).get(identity)
    if not reviewed:
        if kind=='event' and not old_library:return None,'LEGACY_GLOBAL'
        if kind=='notification' and row.get('source')=='ADMIN' and not old_library:return None,'GLOBAL'
        return None,'AMBIGUOUS_'+kind.upper()+'_TENANCY'
    if reviewed.get('approved') is not True or not reviewed.get('approved_by') or not reviewed.get('reason'):
        return None,'REVIEW_APPROVAL_REQUIRED'
    scope=reviewed.get('scope')
    if scope in ['GLOBAL','PLATFORM']:
        if kind=='event' and scope!='GLOBAL':return None,'INVALID_EVENT_SCOPE'
        # Tenant-looking old provenance cannot be discarded by a global mapping.
        if old_library:return None,'AMBIGUOUS_'+kind.upper()+'_TENANCY'
        return {'scope':scope,'library_id':None},'REVIEWED_GLOBAL'
    if scope!='LIBRARY':return None,'UNKNOWN_REVIEW_REQUIRED'
    reference=reviewed.get('legacy_library_id',old_library)
    mapped=plan.get('library_map',{}).get(reference)
    if mapped is None:return None,'EXPLICIT_LIBRARY_MAPPING_REQUIRED'
    try:library_id=str(UUID(mapped))
    except (ValueError,TypeError,AttributeError):return None,'INVALID_LIBRARY_UUID'
    if not library_exists(library_id):return None,'LIBRARY_NOT_FOUND'
    patch={'scope':'LIBRARY','library_id':library_id}
    if kind=='event':patch['visibility']='LIBRARY_MEMBERS' # explicit safe migration policy
    # Migrated notifications without canonical domain/audience remain history
    # only: the action resolver does not manufacture an actionable reference.
    return patch,'LIBRARY_RESOLVABLE'


def run(kind):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--local-development',action='store_true')
    parser.add_argument('--limit',type=int,default=10000)
    parser.add_argument('--report',type=Path,default=ROOT/f'reports/institution_v2d_{kind}_migration.json')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    uri=os.getenv('MONGO_URI');database=os.getenv('MONGO_DB_NAME','luminar_library')
    if args.apply and (not args.local_development or urlparse(uri).hostname not in ['localhost','127.0.0.1','::1']):
        parser.error('Apply requires an explicitly reviewed local-development database. Production apply is not supported.')
    if not 1<=args.limit<=100000:parser.error('Bounded limit must be 1..100000.')
    plan=json.loads(args.plan.read_text(encoding='utf8')) if args.plan else {}
    rows=[];counts={};changed=0;field='event_id' if kind=='event' else 'notification_id'
    with MongoClient(uri,serverSelectionTimeoutMS=5000) as client:
        db=client[database];coll=db['events' if kind=='event' else 'notifications'].with_options(write_concern=WriteConcern(w=1,j=True))
        for row in coll.find({}, {'_id':0,field:1,'scope':1,'library_id':1,'source':1,'revision':1}).sort(field,1).limit(args.limit):
            patch,classification=decision(row,kind,plan,lambda library_id:bool(db.institution_libraries.find_one({'library_id':library_id},{'_id':1})))
            counts[classification]=counts.get(classification,0)+1
            item={field:row.get(field),'classification':classification,'proposed_scope':patch,'applied':False}
            if args.apply and patch:
                query={field:row[field],**{key:row[key] if key in row else {'$exists':False} for key in ['scope','library_id','revision']}}
                patch={**patch,'scope_migration':{'phase':'INSTITUTION_V2D','approved_by':plan['records'][row[field]]['approved_by'],'reason':plan['records'][row[field]]['reason']}}
                result=coll.update_one(query,{'$set':patch})
                item['applied']=result.matched_count==1
                if not item['applied']:item['classification']='CONCURRENT_CHANGE_REVIEW_REQUIRED'
                changed+=result.modified_count
            rows.append(item)
        total=coll.count_documents({})
    report={'mode':'APPLY_LOCAL' if args.apply else 'DRY_RUN','production_apply_supported':False,'library_inference':False,'total':total,'scanned':len(rows),'truncated':total>len(rows),'changed':changed,'classifications':counts,'records':rows}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({key:value for key,value in report.items() if key!='records'}))
