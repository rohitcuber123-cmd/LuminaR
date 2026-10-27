"""Create disabled parser development namespace; preserve every active source."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
R=Path('reports');P='search_v2c_c5d_repair_';C=Path('scratch/search_v2c_c5d_repair/candidate_search')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:f.write(json.dumps(v,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def main():
    assert not C.exists() and not list(R.glob(P+'*'))
    pre=load(R/'search_v2c_c5d_preflight.json')
    assert all(sha(p)==h for p,h in pre['protected_files'].items())
    for phase in ['c5a','c5b','c5c','c5d']:
        frozen=load(R/('search_v2c_'+phase+'_freeze_manifest.json'));assert all(sha(p)==h for p,h in frozen['files'].items())
    protected=dict(pre['protected_files'])
    protected.update({str(p):sha(p) for p in R.glob('search_v2c_c*') if p.is_file() and not p.name.startswith(P)})
    protected.update({str(p):sha(p) for p in Path('scripts').glob('search_v2c_c*.py') if not p.name.startswith(P)})
    C.mkdir(parents=True);(C/'__init__.py').write_text('"""Disabled C5D development candidate. No production import or activation hook."""\n',encoding='utf8')
    copies={}
    for name in ['query_plan','query_constraints','query_numeric','query_repair','query_confidence','query_calibration','query_session']:
        source=Path('search')/(name+'.py');dest=C/(name+'.py')
        text=source.read_text(encoding='utf8').replace('search.query_', 'scratch.search_v2c_c5d_repair.candidate_search.query_')
        dest.write_text(text,encoding='utf8');copies[str(dest)]={'parent':str(source),'parent_sha256':sha(source),'initial_isolated_copy_sha256':sha(dest)}
    write('preflight.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'protected_files':protected,'copies':copies,
       'prior_C5D_preserved':True,'production_source_files':462,'production_activation':False,
       'authorization_sha256':sha(r'C:\Users\balak\.codex\attachments\633233de-194f-4323-a936-b09ba92bc6f7\Pasted text.txt'),
       'contract_basis':'C5D notice audit: producer absent and actual repair evidence missing. Candidate emits existing typed notice only for bounded source-backed grammar repairs; unchanged C4 policy consumes existing repair provenance.',
       'development_data_exposure':'C5C errors and labels previously inspected; candidate evaluation is development assessment, not independent validation.',
       'scoring_definition':'Unchanged frozen C5C scorer and masks; source-copy namespace adapters only.',
       'preflight_discovery_error':'First filename construction used an extra c_ segment; corrected discovery verified all actual freezes before mutation.'})
    print(json.dumps({'preflight':'PASS','protected_files':len(protected),'disabled_copies':len(copies)}))
if __name__=='__main__':main()
