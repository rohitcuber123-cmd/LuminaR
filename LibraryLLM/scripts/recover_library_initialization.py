"""Recover only proven new/empty-library initialization with stopped writers."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.library_canonical_defaults import recover_initialization

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('library_id')
    parser.add_argument('--writers-stopped', action='store_true')
    args = parser.parse_args()
    print(json.dumps(recover_initialization(args.library_id, writers_stopped=args.writers_stopped)))
