import zipfile, pathlib, hashlib, json, tempfile, stat, subprocess, os
z=pathlib.Path(r'D:\SDC\LuminaR_research_documentation_20261031T141713Z\research_paper\20261031T140041Z_606f0df_15.zip'); out=pathlib.Path('reports/module15_gpu_v2'); out.mkdir(exist_ok=True)
def write(n,d): (out/(n+'.json')).write_text(json.dumps(d,indent=2,default=str),encoding='utf8')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(z) as f:
 items=[]
 for i in f.infolist():
  p=pathlib.PurePosixPath(i.filename); mode=i.external_attr>>16
  if p.is_absolute() or '..' in p.parts or '\\' in i.filename or ':' in i.filename or stat.S_ISLNK(mode) or p.suffix.lower() in {'.exe','.dll','.bat','.cmd','.ps1','.py','.js','.vbs','.com','.msi'}: raise ValueError('Unsafe archive entry '+i.filename)
  items.append({'name':i.filename,'bytes':i.file_size,'timestamp':i.date_time,'sha256':hashlib.sha256(f.read(i)).hexdigest() if not i.is_dir() else None})
 with tempfile.TemporaryDirectory(prefix='luminar-module15-') as tmp:
  f.extractall(tmp)
  base=pathlib.Path(tmp)/'20261031T140041Z_606f0df_15'; snap=json.loads((base/'15_snapshot.json').read_text()); tests=json.loads((base/'15_test_results.json').read_text()); docs={p.name:p.read_text(encoding='utf8') for p in base.iterdir() if p.is_file()}
  prior=json.loads(pathlib.Path('reports/module15_gpu_verification/grounding_contract_regression.json').read_text())
  write('historical_snapshot_reconciliation',{'snapshot':snap,'five_historical_checks':tests,'gpu_prior_contract':prior,'archive_docs_read':list(docs),'match_known_baseline':snap['head']=='606f0dfce3970bea8e6fc2b62d243433d1a66b8a' and len(tests['checks'])==5 and all(x['passed'] for x in tests['checks']),'no_archive_code_executed':True})
write('archive_inventory',{'filename':str(z),'sha256':digest(z),'size_bytes':z.stat().st_size,'entries':items,'module':'15','unsafe_entries':0,'extraction':'Validated and extracted to temporary directory outside app, then temporary directory removed'})
def cmd(*a):return subprocess.check_output(a,text=True,encoding='utf8',errors='replace').strip()
status=cmd('git','status','--porcelain=v1','-uall').splitlines(); source=['assistant/api.py','assistant/qwen.py','assistant/orchestrator.py','rag/api.py','rag/qa.py','rag/llm.py','rag/retriever.py','rag/reranker.py','search/luminar_search.py','tests/contracts/rag_grounding_v2o2.py']
write('working_tree_baseline',{'branch':cmd('git','branch','--show-current'),'head':cmd('git','rev-parse','HEAD'),'tracked_dirty':[x for x in status if not x.startswith('??')],'untracked':[x for x in status if x.startswith('??') and 'module15_gpu_v2/' not in x],'protected_sha256':{x:digest(pathlib.Path(x)) for x in source},'preexisting_verification':'reports/module15_gpu_verification/'})
