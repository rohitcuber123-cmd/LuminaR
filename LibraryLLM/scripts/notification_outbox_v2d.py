"""Bounded operator inspection/drain of committed notification intents."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.services.institution_repository import collection
from backend.services.tenant_notification_service import materialize

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--drain',action='store_true')
    parser.add_argument('--limit',type=int,default=100)
    args=parser.parse_args()
    if not 1<=args.limit<=500:parser.error('limit must be 1..500')
    summary=list(collection('notification_outbox').aggregate([{'$group':{'_id':{'state':'$state','error':'$last_error_code'},'count':{'$sum':1}}}]))
    print(json.dumps({'summary':summary,'drain':materialize(args.limit) if args.drain else None}))
