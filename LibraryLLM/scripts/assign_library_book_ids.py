"""Assign missing canonical identities/accessions to eligible explicitly mapped legacy records.

Uses the same idempotent migration markers; preserves original inventory rather
than altering IDs still referenced by legacy circulation. Dry-run by default.
"""
from inventory_v2a_migration import main

if __name__ == '__main__':
    main(__doc__)
