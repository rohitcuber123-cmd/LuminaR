"""Fresh current-tree production RAG, private-data and lexical regressions."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o2_rag_checks.py').read_text().replace('reports/institution_v2o2_','reports/institution_v2o3_closure_')
exec(compile(source,str(ROOT/'scripts/institution_v2o2_rag_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
