"""Explicit lexical status, base validation and delta initialization commands."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from search.lexical_delta import initialize_delta,LexicalDeltaWriter,LexicalOverlayStore
from search.lexical_store import LexicalSearchStore,default_path
from search.sync_queue import SyncQueue,index_root


def main():
    load_dotenv(ROOT/'.env')
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('status','init-delta','process-once','validate-base'))
    parser.add_argument('--checkpoint',type=int)
    parser.add_argument('--validation',choices=('startup','quick','full'),default='quick')
    parser.add_argument('--apply',action='store_true',
                        help='Required for process-once, which writes the lexical delta')
    parser.add_argument('--root',default=str(default_path()))
    args=parser.parse_args()
    if args.command=='process-once' and not args.apply:
        parser.error('process-once writes the lexical delta and requires --apply')
    root=Path(args.root)
    source=os.getenv('MONGO_DB_NAME','luminar_library')
    if args.command=='init-delta':
        if args.checkpoint is None: parser.error('init-delta requires --checkpoint')
        base=LexicalSearchStore(root,expected_source_db=source)
        if not base.health()['lexical_available']: raise RuntimeError(base.health())
        try:
            queue=SyncQueue(index_root())
            print(json.dumps(initialize_delta(root,base.manifest,args.checkpoint,queue),indent=2))
        finally: base.close()
    elif args.command=='validate-base':
        store=LexicalSearchStore(root,expected_source_db=source,validation_mode=args.validation)
        try:
            print(json.dumps({'validation':args.validation,'health':store.health(),
                              'timings':store.startup_timings},indent=2))
            if not store.health()['lexical_available']: raise RuntimeError('Lexical validation failed')
        finally: store.close()
    elif args.command=='status':
        store=LexicalOverlayStore(root,expected_source_db=source,
                                  event_queue=SyncQueue(index_root()))
        try:
            print(json.dumps(store.health(),indent=2))
        finally: store.close()
    else:
        from pymongo import MongoClient
        with MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017')) as client:
            writer=LexicalDeltaWriter(root,client[source].books,SyncQueue(index_root()),
                                      expected_source_db=source)
            try:
                processed=writer.process_once()
                print(json.dumps({'processed':processed,'status':writer.status()},indent=2))
            finally: writer.close()


if __name__=='__main__': main()
