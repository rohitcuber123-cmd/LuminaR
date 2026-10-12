"""Correct the collection-name typo before any product-code edits; keep all hashes."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'reports/full_product_convergence_baseline.json'
data=json.loads(path.read_text(encoding='utf8'))
assert not data['test_records'], 'Never overwrite an already captured TEST baseline.'
load_dotenv(ROOT/'.env')
with MongoClient(os.getenv('MONGO_URI'),serverSelectionTimeoutMS=5000) as client:
    db=client['luminar_library']; scope={'library_id':'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'}
    data['test_records']=list(db.institution_library_books.find(scope,{'_id':0}).sort('library_book_id',1))
    data['test_holdings']=list(db.institution_holdings.find(scope,{'_id':0}).sort('library_book_id',1))
data['baseline_correction']='Before product edits: use institution_library_books / institution_holdings; source/artifact/prior report hashes unchanged.'
path.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
print('TEST baseline:',len(data['test_records']),'records;',len(data['test_holdings']),'holdings.')
