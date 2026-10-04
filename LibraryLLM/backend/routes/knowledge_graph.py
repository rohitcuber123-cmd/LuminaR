"""Authenticated, read-only experiment; existing recommendation service untouched."""
import logging
import hashlib
import re
from fastapi import APIRouter,Depends,HTTPException,Query,Path
from pydantic import BaseModel,ConfigDict,Field
import requests
from backend.dependencies import get_current_user,security
from backend.services.identity_service import current_identity
from backend.database.mongodb import books_collection,issues_collection,reservations_collection
from knowledge_graph.core import CatalogueGraph,public_book,terms,canonical
from knowledge_graph.metrics import compare
from search.catalogue import current_books
from backend.services.availability_service import get_availability_context

router=APIRouter(prefix='/experimental/kg',tags=['Experimental catalogue graph'])
product_router=APIRouter(prefix='/kg',tags=['Related books'])
graph=CatalogueGraph()
LOG=logging.getLogger(__name__)

def identity(user=Depends(get_current_user)):
    try:current=current_identity(user)
    except (ValueError,KeyError,TypeError):current=None
    if current is None:raise HTTPException(401,'Your session is no longer active.')
    return current

class SeedRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    work_id:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')
    limit:int=Field(default=10,ge=1,le=50)

def guarded(function,*args,**kwargs):
    try:return function(*args,**kwargs)
    except FileNotFoundError:raise HTTPException(503,'The catalogue graph is not ready. Build KG1 first.') from None
    except KeyError:raise HTTPException(404,'This book is not in the catalogue graph.') from None

def exclusions(user):
    uid=int(user['sub'])
    issued=issues_collection.find({'user_id':uid,'status':'ISSUED'},{'_id':0,'work_id':1})
    reserved=reservations_collection.find({'user_id':uid,'status':{'$in':['ACTIVE','READY_FOR_PICKUP']}},{'_id':0,'work_id':1})
    return {r['work_id'] for r in [*issued,*reserved] if r.get('work_id')}

def features_current(snapshot,live):
    if any(set(terms(snapshot[field]))!=set(terms(live.get(field))) for field in ['authors','subjects']):return False
    if 'description_hash' in snapshot:
        return snapshot['description_hash']==hashlib.sha256(canonical(live.get('description') or '').encode()).hexdigest()
    return True

def recommendation(request,user):
    current=current_books(books_collection,[request.work_id])
    if request.work_id not in current:raise HTTPException(404,'This book is no longer in the searchable catalogue.')
    seed=guarded(graph.book,request.work_id)
    if not features_current(seed,current[request.work_id]):
        raise HTTPException(409,'This book’s metadata changed. Rebuild the graph before comparing it.')
    result=guarded(graph.more_like_this,request.work_id,request.limit,exclusions(user))
    live=current_books(books_collection,[r['work_id'] for r in result['recommendations']])
    result['recommendations']=[r for r in result['recommendations'] if r['work_id'] in live and
        features_current(r,live[r['work_id']])]
    result['seed']=public_book(current[request.work_id])
    for r in result['recommendations']:r['title']=live[r['work_id']]['title']
    result['exploration']=graph.exploration(result)
    result['snapshot']=guarded(graph.meta)
    result['scope']='Catalogue metadata only; active loans and reservations excluded for the signed-in reader.'
    return result

@router.get('/meta')
def meta(user=Depends(identity)):return guarded(graph.meta)

@router.get('/books')
def books(q:str=Query(default='',max_length=120),limit:int=Query(default=20,ge=1,le=50),user=Depends(identity)):
    if re.fullmatch(r'[A-Za-z0-9_-]{1,128}',q) and q.startswith('OL'):
        candidates=[guarded(graph.book,q)]
    else:candidates=guarded(graph.lookup,q,limit)
    live=current_books(books_collection,[b['work_id'] for b in candidates])
    return {'books':[public_book(live[b['work_id']]) for b in candidates if b['work_id'] in live]}

@router.post('/more-like-this')
def more_like_this(request:SeedRequest,user=Depends(identity)):return recommendation(request,user)

@product_router.get('/books/{work_id}/more-like-this')
def product_more_like_this(work_id:str=Path(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_-]+$'),
                          limit:int=Query(default=10,ge=1,le=50),user=Depends(identity)):
    """Reuse the KG query, then refresh display facts through Core authority."""
    try:
        result=recommendation(SeedRequest(work_id=work_id,limit=limit),user)
    except HTTPException as exc:
        if exc.status_code==409:
            raise HTTPException(409,'Related-book data for this title is being refreshed.') from None
        raise
    live=current_books(books_collection,[book['work_id'] for book in result['recommendations']])
    cards=[]
    for related in result['recommendations']:
        book=live.get(related['work_id'])
        if book is None or not features_current(related,book):
            continue
        availability=get_availability_context(book)
        cards.append({**public_book(book),'book_id':book.get('book_id'),
            'average_rating':book.get('average_rating'),'rating_count':book.get('rating_count'),
            'shelf_location':book.get('shelf_location'),
            'available_copies':availability['available_copies'],'total_copies':availability['total_copies'],
            'availability_source':availability['source'],'score':related['score'],'reason_paths':related['reason_paths']})
    return {'seed_work_id':work_id,'seed':result['seed'],'graph_version':result['snapshot']['version'],
            'candidate_count':result['candidate_count'],'recommendations':cards,'limit':limit,
            'has_more':False,'snapshot_at':result['snapshot']['created_at']}

@router.post('/compare')
def comparison(request:SeedRequest,user=Depends(identity),credentials=Depends(security)):
    result=recommendation(request,user)
    try:
        response=requests.post('http://127.0.0.1:8004/recommendations/from-book',json=request.model_dump(),
                               headers={'Authorization':'Bearer '+credentials.credentials},timeout=90)
        response.raise_for_status();existing=response.json()['recommendations']
    except (requests.RequestException,KeyError,ValueError):
        raise HTTPException(503,'The existing recommender is unavailable; no comparison was measured.') from None
    result['existing']=[public_book(b) for b in existing]
    result['metrics']=compare(result['existing'],result['recommendations'])
    return result
