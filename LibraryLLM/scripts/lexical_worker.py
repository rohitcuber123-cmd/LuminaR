"""Run lexical queue consumption without importing or loading FAISS/Search.

The worker requires an explicit --apply and the opt-in sync flag. Core and this
process must share MONGO_DB_NAME and LUMINAR_SEARCH_INDEX_DIR.
"""
import argparse
import logging
import os
from pathlib import Path
import sys
import time

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--poll-seconds', type=float, default=2)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    if not args.apply or os.getenv('LUMINAR_LEXICAL_SYNC_ENABLED', 'false').lower() != 'true':
        parser.error('worker requires --apply and LUMINAR_LEXICAL_SYNC_ENABLED=true')
    if args.poll_seconds < 0.1:
        parser.error('--poll-seconds must be at least 0.1')

    from pymongo import MongoClient
    from search.lexical_delta import LexicalDeltaWriter
    from search.lexical_store import default_path
    from search.sync_queue import SyncQueue, index_root

    source = os.getenv('MONGO_DB_NAME', 'luminar_library')
    root = args.root or default_path()
    logging.basicConfig(level=logging.INFO)
    with MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'),
                     serverSelectionTimeoutMS=3000) as client:
        client.admin.command('ping')
        writer = LexicalDeltaWriter(root, client[source].books,
                                    SyncQueue(index_root()), expected_source_db=source)
        try:
            while True:
                writer.process_once()
                time.sleep(args.poll_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            writer.close()


if __name__ == '__main__':
    main()
