"""Same full product inventory, current2P plus2P.1; owned fallback isolation."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2p_checks.py').read_text(encoding='utf8')
marker='owned=None'
source=source.replace(marker,"source=source.replace(\"results = []\\n    for name, files\", \"if (ROOT/'tests/institution_v2p1').exists(): groups['institution_v2p1'] = ['tests/institution_v2p1']\\n    results = []\\n    for name, files\")\n"+marker)
# Rename output namespaces only; keep2P test group names and accepted assertions.
source=source.replace("owned=None", "source=source.replace('.scratch/institution-v2p/', '.scratch/institution-v2p1/').replace('reports/institution_v2p_', 'reports/institution_v2p1_').replace(\"f'institution_v2p_{a.tag}_generated_\",\"f'institution_v2p1_{a.tag}_generated_\")\nowned=None")
source=source.replace("owned='luminar_v2p_regression_'", "owned='luminar_v2p1_regression_'").replace("startswith('luminar_v2p_regression_')", "startswith('luminar_v2p1_regression_')").replace('institution-v2p/regression','institution-v2p1/regression').replace('reports/institution_v2p_{sys.argv','reports/institution_v2p1_{sys.argv')
exec(compile(source,str(ROOT/'scripts/institution_v2p_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
