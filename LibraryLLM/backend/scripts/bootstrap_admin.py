"""Retired legacy role bootstrap. Provision identity, then approve explicit authority."""

def bootstrap_first_admin(*args, **kwargs):
    raise ValueError('Legacy ADMIN bootstrap is retired. Create a verified identity and use scripts/migrate_management_authority.py with an explicitly approved mapping.')

def main():
    raise SystemExit('Legacy ADMIN bootstrap is retired. Use an explicitly approved management authority mapping; no global role grants authority.')

if __name__ == '__main__':
    main()
