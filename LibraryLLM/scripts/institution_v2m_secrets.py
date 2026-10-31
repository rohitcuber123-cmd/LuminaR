"""DPAPI fixture orchestration. No plaintext secret file, argv or returned report values."""
import json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def protect(root,path,secret):
    payload={'fixture_root':str(root),'secret_path':str(path),'secret':secret}
    p=subprocess.run(command('protect'),
        input=json.dumps(payload),capture_output=True,text=True,timeout=20)
    if p.returncode:raise RuntimeError('DISPOSABLE_SECRET_FIXTURE_UNAVAILABLE')
    result=json.loads(p.stdout)
    raw=Path(path).read_bytes()
    result['plaintext_absent_from_ciphertext']=secret.encode() not in raw and secret.encode('utf-16le') not in raw
    assert result['recovered_matches'] and result['file_protected'] and result['directory_protected'] and result['plaintext_absent_from_ciphertext']
    return result


def command(mode):return [shutil.which('pwsh.exe') or 'powershell.exe','-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/institution_v2m_secret_fixture.ps1'),'-Mode',mode]
