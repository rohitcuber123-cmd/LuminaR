"""Candidate full transport + executable page boundary. No product code executes."""
import hashlib
import json
from pathlib import Path
import subprocess


def assert_staff_contract(root, *, compiler_root=None):
    root=Path(root)
    manifest=json.loads(Path(__file__).with_suffix('.json').read_text())
    for name,expected in manifest['full_transport_modules'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected, f'FULL_TRANSPORT_CHANGED:{name}'
    for name,expected in manifest['backend_authority'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected, f'BACKEND_AUTHORITY_CHANGED:{name}'
    compiler=Path(compiler_root or Path(__file__).resolve().parents[2])/'frontend/node_modules/typescript'
    result=subprocess.run(['node',str(Path(__file__).with_suffix('.cjs')),str(root/'frontend/src/pages/LibraryIntelligence.tsx'),str(compiler),str(Path(__file__).with_suffix('.json'))],
                          capture_output=True,text=True,timeout=20,check=True)
    verdict=json.loads(result.stdout)
    assert verdict['ok'], verdict['errors']
    return verdict
