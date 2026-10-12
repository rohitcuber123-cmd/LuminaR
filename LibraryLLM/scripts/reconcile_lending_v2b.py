import argparse
import json
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.lending_v2b_operations import reconcile, recover, rollback


def main():
    parser = argparse.ArgumentParser(description='Read-only by default; offline recovery/rollback require explicit application.')
    parser.add_argument('--library-id', type=UUID, required=True)
    parser.add_argument('--action', choices=['reconcile', 'recover', 'rollback'], default='reconcile')
    parser.add_argument('--apply', action='store_true'); parser.add_argument('--writers-stopped', action='store_true')
    args = parser.parse_args(); library_id = str(args.library_id)
    result = reconcile(library_id) if args.action == 'reconcile' else (recover if args.action == 'recover' else rollback)(library_id, apply=args.apply, writers_stopped=args.writers_stopped)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get('ok', result.get('safe', True)) else 2


if __name__ == '__main__':
    raise SystemExit(main())
