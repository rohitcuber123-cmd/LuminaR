"""Reviewable diff limited to this continuation's application/test changes."""
from pathlib import Path
import difflib,hashlib
R=Path(__file__).resolve().parents[1];patch=[]
for name in ['assistant/qwen.py','rag/api.py','rag/services/library_asset_pipeline.py']:
 before=R/'.scratch/institution-v2q/continuation/before'/('library_asset_pipeline.py' if name.endswith('library_asset_pipeline.py') else name)
 patch.extend(difflib.unified_diff(before.read_text(encoding='utf8').splitlines(True),(R/name).read_text(encoding='utf8').splitlines(True),fromfile='a/'+name,tofile='b/'+name))
for name in ['rag/citation_boundary.py','tests/institution_v2q_ai/test_v2q1c_citations.py','tests/institution_v2q_ai/test_v2q1c_reference_prompt.py']:
 patch.extend(difflib.unified_diff([], (R/name).read_text(encoding='utf8').splitlines(True),fromfile='/dev/null',tofile='b/'+name))
p=R/'reports/institution_v2q1c_unprotected_changes.patch';p.write_text(''.join(patch),encoding='utf8');print(hashlib.sha256(p.read_bytes()).hexdigest())
