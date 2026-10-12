"""Adapt historical test fixtures to explicitly model historical installations."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace(path, old, new):
    target = ROOT / path
    text = target.read_text(encoding='utf8')
    if old not in text:
        raise ValueError('Expected edit not found: ' + path)
    target.write_text(text.replace(old, new), encoding='utf8')

if __name__ == '__main__':
    for phase in ['institution_v2a', 'institution_v2b', 'institution_v2c']:
        replace(f'tests/{phase}/conftest.py', "        return response.json()['library']['library_id']", """        library_id = response.json()['library']['library_id']
        # These accepted suites exercise historical snapshot/cutover semantics.
        # Fresh registration is tested independently with canonical defaults.
        for name in ['lending_config', 'v2c_config', 'fee_policies', 'lending_operations']:
            db['institution_' + name].delete_many({'library_id': library_id})
        return library_id""")
    replace('tests/library_catalogue_experience/test_catalogue.py', "        call(client, 1, 'POST', base + '/staff/lending/activate', command())\n        call(client, 1, 'POST', base + '/staff/reservations-fees/activate', command())", "        # Fresh registration already provisions all canonical subsystems.")
    for phase in ['frontend_workspace', 'dashboard_convergence']:
        target = ROOT / f'tests/{phase}/conftest.py'
        text = target.read_text(encoding='utf8')
        start = text.index("        for path in ['/staff/lending/activate', '/staff/reservations-fees/activate']:")
        end = text.index('\n', text.index('\n', start) + 1)
        target.write_text(text[:start] + '        # Fresh registrations are canonical; no fake cutover.\n' + text[end+1:], encoding='utf8')
    replace('frontend/tests/institution-inventory.test.tsx', '/Counts below are inventory snapshots/', '/Inventory counts are snapshots/')
    replace('frontend/src/components/LibraryShells.tsx', 'PageHeading eyebrow="Staff workspace" title="Overview"', 'PageHeading title="Overview"')
    replace('frontend/src/components/LibraryShells.tsx', "<strong>{card.value ?? 'Not enabled'}</strong>", "{card.value == null ? <span className=\"ui-badge workspace-status\">Setup required</span> : <strong>{card.value}</strong>}")
    replace('frontend/src/components/LibraryShells.tsx', 'Staff can review requests after approval circulation is enabled.', 'Staff review borrow requests and confirm physical returns in Circulation.')
    replace('frontend/src/pages/LibraryCirculation.tsx', 'Approval circulation · {mode}', "{mode === 'LEGACY' ? 'Circulation setup required' : 'Circulation needs recovery'}")
    replace('frontend/src/pages/LibraryReservationsFees.tsx', 'Reservations and fees · {mode}', "{mode === 'LEGACY' ? 'Reservations and fees setup required' : 'Reservations and fees need recovery'}")
