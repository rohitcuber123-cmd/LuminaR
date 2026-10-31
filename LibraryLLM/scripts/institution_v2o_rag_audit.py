"""Hash/history evidence only. Never changes protected RAG source or expectations."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'reports/institution_v2o_rag_hash_evidence.json').read_text())
history=[]
commits=subprocess.check_output(['git','log','--format=%H','--','rag/qa.py'],cwd=ROOT,text=True).splitlines()
for commit in commits:
    payload=subprocess.check_output(['git','show',commit+':LibraryLLM/rag/qa.py'],cwd=ROOT)
    history.append({'commit':commit,'subject':subprocess.check_output(['git','show','-s','--format=%s',commit],cwd=ROOT,text=True).strip(),
                    'git_blob_sha256':hashlib.sha256(payload).hexdigest().upper(),
                    'CRLF_sha256':hashlib.sha256(payload.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest().upper()})
diff=subprocess.check_output(['git','diff',commits[-1]+'..HEAD','--','rag/qa.py'],cwd=ROOT,text=True)
(ROOT/'reports/institution_v2o_rag_source_diff.txt').write_text(diff)
(ROOT/'reports/institution_v2o_rag_hash_history.json').write_text(json.dumps({'files':rows,'history':history,'protected_source_modified_in_O':False,
    'finding':'qa.py committed additions: document identity detection, definition evidence selection/category and unsupported-document citation suppression. Not generated/environment-only data.',
    'status':'REQUIRES_APPROVAL','reason':'Reverting would remove existing document-grounding behavior; updating frozen hashes or suppressing assertion is prohibited.'},indent=2))
