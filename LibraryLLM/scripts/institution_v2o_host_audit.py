"""Read-only current endpoint/ownership/ACL snapshot into O namespace."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2m_host_audit.py').read_text().replace('reports/institution_v2m_host_audit.json','reports/institution_v2o_host_audit.json')
exec(compile(source,str(ROOT/'scripts/institution_v2m_host_audit.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
source=(ROOT/'scripts/institution_v2n_boundary.py').read_text().replace('institution_v2n_host_audit.json','institution_v2o_host_audit.json').replace('institution_v2n_boundary.json','institution_v2o_boundary.json')
exec(compile(source,str(ROOT/'scripts/institution_v2n_boundary.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
