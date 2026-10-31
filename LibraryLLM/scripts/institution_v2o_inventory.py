"""Whole source inventory plus observed per-process constructor coverage."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_inventory.py').read_text().replace('reports/institution_v2n_client_inventory.json','reports/institution_v2o_client_inventory.json')
exec(compile(source,str(ROOT/'scripts/institution_v2n_inventory.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
inventory=json.loads((ROOT/'reports/institution_v2o_client_inventory.json').read_text())
traces=[]
for path in (ROOT/'reports').glob('institution_v2o_*commands.json'):
    value=json.loads(path.read_text())
    if isinstance(value,dict):traces.append({'evidence':path.name,**value})
coverage=[]
for row in inventory['clients']:
    observed=[t['evidence'] for t in traces if any(any(row['path']+':' in frame for frame in c['source']) for c in t.get('clients',[]))]
    coverage.append({**row,'runtime_evidence':observed,'coverage':'OBSERVED_OWNED_PROCESS' if observed else 'SOURCE_ONLY_NOT_EXECUTED',
                     'deployed_owner':'NOT_VERIFIED','credential_source':'Explicit URI env/arguments; values omitted','teardown':'Observed per-client closed field in referenced trace; source-only sites require individual qualification.'})
(ROOT/'reports/institution_v2o_mongo_runtime_coverage.json').write_text(json.dumps({'source_clients':coverage,'runtime_traces':[t['evidence'] for t in traces],
    'scope':'Actual instantiated clients/command source stacks in owned processes, not just source search. Primary runtime identities Core/Search/resident native/Recommendation/RAG/reader/writer plus qualified CLI negatives.',
    'deployed_inventory_complete':False,'unknowns':['Actual deployed app/service ownership','Historical/maintenance entrypoints not executed','All conditionally imported paths and production-equivalent full catalogue workload']},indent=2))
