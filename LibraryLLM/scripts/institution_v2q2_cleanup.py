"""Remove only the explicitly owned disposable DB and resolved owned lab path."""
from pathlib import Path
import json,psutil,socket,shutil
from pymongo import MongoClient
R=Path(__file__).resolve().parents[1];S=(R/'.scratch/institution-v2q/validator-review/lab').resolve()

def main():
 assert S==Path('D:/SDC/LibraryLLM/.scratch/institution-v2q/validator-review/lab').resolve()
 assert S.is_relative_to((R/'.scratch/institution-v2q/validator-review').resolve())
 cfg=json.loads((S/'configuration.json').read_text());assert cfg['database'].startswith('luminar_v2q2_') and cfg['database']!='luminar_library'
 for port in [18005,18017]:
  with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0,'Stop only owned services before fixture removal'
 with MongoClient('mongodb://127.0.0.1:27017') as client:
  assert cfg['database'] in client.list_database_names();client.drop_database(cfg['database'])
  removed=cfg['database'] not in client.list_database_names()
 shutil.rmtree(S)
 config=(R/'frontend/.scratch/q2-vite.config.ts').resolve();assert config.parent==(R/'frontend/.scratch').resolve();config.unlink()
 (R/'reports/institution_v2q2_fixture_cleanup.json').write_text(json.dumps({'database':cfg['database'],'database_removed':removed,'owned_lab_path_removed':not S.exists(),'owned_frontend_config_removed':not config.exists(),'preserved_before_source_snapshot':'.scratch/institution-v2q/validator-review/before/assistant/qwen.py','no_live_database_cleanup':True},indent=2))

if __name__=='__main__':main()
