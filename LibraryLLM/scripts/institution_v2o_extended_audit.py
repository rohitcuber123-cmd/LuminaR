"""Read-only Windows inventory with bounded provider timeout and sanitized errors."""
import json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
try:
    p=subprocess.run([shutil.which('pwsh.exe'),'-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/institution_v2o_extended_audit.ps1')],capture_output=True,text=True,timeout=45)
    value=json.loads(p.stdout) if p.returncode==0 else {'status':'NOT_VERIFIED','error':'Metadata provider failed; no raw output recorded'}
except subprocess.TimeoutExpired:value={'status':'NOT_VERIFIED','error':'Bounded metadata provider timeout; no policy changes attempted'}
(ROOT/'reports/institution_v2o_extended_audit.json').write_text(json.dumps(value,indent=2))
print('Read-only extended network/owner/child-ACL evidence saved')
