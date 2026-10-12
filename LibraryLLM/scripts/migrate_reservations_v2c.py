import argparse
import json
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.institution_v2c_migration import plan, apply


def main(kind='reservations'):
    parser = argparse.ArgumentParser(); parser.add_argument('--library-id', required=True, type=UUID)
    parser.add_argument('--legacy-library-id', required=True); parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true'); parser.add_argument('--idempotency-key', type=UUID)
    args = parser.parse_args()
    if args.apply and not args.idempotency_key: parser.error('--apply requires --idempotency-key UUID')
    result = apply(str(args.library_id), args.legacy_library_id, kind, writers_stopped=args.writers_stopped, idempotency_key=str(args.idempotency_key)) if args.apply else plan(str(args.library_id), args.legacy_library_id, kind)
    print(json.dumps(result, indent=2, default=str)); return 0 if result['ok'] else 2


if __name__ == '__main__': raise SystemExit(main())
