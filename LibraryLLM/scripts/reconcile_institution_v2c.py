import argparse
import json
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.institution_v2c_operations import reconcile, recover, rollback

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--library-id', required=True, type=UUID)
    parser.add_argument('--operation', choices=['reconcile', 'recover', 'rollback'], default='reconcile')
    parser.add_argument('--apply', action='store_true'); parser.add_argument('--writers-stopped', action='store_true')
    args = parser.parse_args()
    result = reconcile(str(args.library_id)) if args.operation == 'reconcile' else (recover if args.operation == 'recover' else rollback)(str(args.library_id), apply=args.apply, writers_stopped=args.writers_stopped)
    print(json.dumps(result, indent=2, default=str)); raise SystemExit(0 if result.get('ok', result.get('safe')) else 2)
