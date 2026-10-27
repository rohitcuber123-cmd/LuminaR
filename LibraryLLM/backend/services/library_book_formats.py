"""Derived book capabilities from real stock and authorized READY assets only."""
from backend.services.institution_repository import collection


def unstocked_origin(library_id, book_id):
    """Creation receipt proves intentional absence, rather than lost physical data.

    This is immutable creation provenance, not the current format authority.
    """
    receipt=collection('lending_operations').find_one({'library_id':library_id,'library_book_id':book_id,
        'operation_type':'LIBRARY_BOOK_CREATED','state':'COMMITTED'}, {'_id':0,'result.holding':1,'result.has_physical':1})
    if receipt is not None:
        return receipt.get('result',{}).get('has_physical') is False and receipt['result'].get('holding') is None
    return bool(collection('audit').find_one({'library_id':library_id,'event':'LIBRARY_BOOK_CREATED',
        'metadata.library_book_id':book_id,'metadata.holding_id':{'$exists':False}}, {'_id':1}))


def capabilities(library_id, book_id, holding, *, staff=False):
    query={'library_id':library_id,'library_book_id':book_id,'status':'READY'}
    if not staff:query['visibility']='MEMBERS'
    assets=list(collection('library_assets').find(query,{'_id':0,'asset_id':1}).limit(2))
    physical=holding is not None;online=bool(assets)
    # A single authorized resource can be opened directly. Multiple resources
    # require an explicit choice in the book's Digital Resources section.
    return {'has_physical':physical,'has_online':online,'online_asset_id':assets[0]['asset_id'] if len(assets)==1 else None,
        'book_format':'PHYSICAL_AND_DIGITAL' if physical and online else 'DIGITAL_ONLY' if online else 'PHYSICAL_ONLY' if physical else 'UNAVAILABLE'}


def format_pipeline(library_id, *, staff=False):
    asset_query = {'library_id': library_id, 'status': 'READY', '$expr': {'$eq': ['$library_book_id', '$$book']}}
    if not staff: asset_query['visibility'] = 'MEMBERS'
    return [
        {'$lookup': {'from': collection('holdings').name, 'let': {'book': '$library_book_id'},
            'pipeline': [{'$match': {'library_id': library_id, '$expr': {'$eq': ['$library_book_id', '$$book']}}}, {'$project': {'_id': 0}}], 'as': '_physical'}},
        {'$set': {'holding': {'$ifNull': [{'$arrayElemAt': ['$_physical', 0]}, None]}}},
        {'$lookup': {'from': collection('library_assets').name, 'let': {'book': '$library_book_id'},
            'pipeline': [{'$match': asset_query}, {'$project': {'_id': 0, 'asset_id': 1}}, {'$limit': 2}], 'as': '_online'}},
        {'$set': {'has_physical': {'$ne': ['$holding', None]}, 'has_online': {'$gt': [{'$size': '$_online'}, 0]},
            'online_asset_id': {'$cond': [{'$eq': [{'$size': '$_online'}, 1]}, {'$arrayElemAt': ['$_online.asset_id', 0]}, None]}}},
        {'$set': {'book_format': {'$switch': {'branches': [
            {'case': {'$and': ['$has_physical', '$has_online']}, 'then': 'PHYSICAL_AND_DIGITAL'},
            {'case': '$has_online', 'then': 'DIGITAL_ONLY'},
            {'case': '$has_physical', 'then': 'PHYSICAL_ONLY'}], 'default': 'UNAVAILABLE'}}}},
        {'$unset': ['_physical', '_online']},
    ]


def unstocked_origin_pipeline(library_id):
    """Bulk equivalent of unstocked_origin, limited to missing-holding rows."""
    missing={'$eq':[{'$ifNull':['$holding.holding_id',None]},None]}
    return [
        {'$lookup':{'from':collection('lending_operations').name,
            'let':{'book':'$library_book_id','missing':missing},
            'pipeline':[{'$match':{'library_id':library_id,'operation_type':'LIBRARY_BOOK_CREATED','state':'COMMITTED',
                '$expr':{'$and':['$$missing',{'$eq':['$library_book_id','$$book']}]}}},
                {'$project':{'_id':0,'result.has_physical':1,'result.holding':1}},{'$limit':1}], 'as':'_creation_receipt'}},
        {'$lookup':{'from':collection('audit').name,
            'let':{'book':'$library_book_id','missing':missing,'no_receipt':{'$eq':[{'$size':'$_creation_receipt'},0]}},
            'pipeline':[{'$match':{'library_id':library_id,'event':'LIBRARY_BOOK_CREATED','metadata.holding_id':{'$exists':False},
                '$expr':{'$and':['$$missing','$$no_receipt',{'$eq':['$metadata.library_book_id','$$book']}]}}},
                {'$project':{'_id':1}},{'$limit':1}], 'as':'_creation_audit'}},
        {'$set':{'_unstocked_origin':{'$cond':[{'$gt':[{'$size':'$_creation_receipt'},0]},
            {'$and':[{'$eq':[{'$arrayElemAt':['$_creation_receipt.result.has_physical',0]},False]},
                     {'$eq':[{'$ifNull':[{'$arrayElemAt':['$_creation_receipt.result.holding',0]},None]},None]}]},
            {'$gt':[{'$size':'$_creation_audit'},0]}]}}},
        {'$unset':['_creation_receipt','_creation_audit']},
    ]
