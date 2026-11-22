"""Fresh evidence for reading access; inventory counts never imply digital rights."""
from fastapi import HTTPException
from contextlib import contextmanager
from backend.services import library_catalogue_experience as catalogue
from backend.services import library_asset_service as assets
from backend.services.institution_repository import collection


@contextmanager
def authority(library_id,actor,staff):
    with catalogue.read_context(library_id,actor,staff=staff) as state:
        if state[2]:
            yield
        else:
            with catalogue.library_mutation(library_id,wait_seconds=30,durable=True):
                assets.fresh_guard(library_id,actor,staff=staff,locked=True)
                yield


def unknown(work_id, library_id=None):
    # None hides inaccessible/nonpublic asset existence as well as absent evidence.
    return dict(work_id=work_id, library_id=library_id, catalogue_present=True,
        resource_link_present=False, asset_present=None, access_authorized=None,
        full_text_accessible=None, status='UNKNOWN', resources=[])


def library_status(library_id, book_id, actor, *, staff=False):
    with authority(library_id,actor,staff):
        books=list(collection('library_books').aggregate([*catalogue.usable(library_id,staff=staff),
            {'$match':{'library_book_id':book_id}}, {'$limit':1}]))
        if not books:raise HTTPException(404,'Book not found in this library.')
        result=unknown(book_id,library_id)
        query={'library_id':library_id,'library_book_id':book_id,'status':'READY'}
        if not staff:query['visibility']='MEMBERS'
        # Bounded, visible, canonical linked assets only. No global-ID fallback.
        for row in collection(assets.ASSETS).find(query,{'asset_id':1}).limit(10):
            try:
                asset=assets.authorize_asset(library_id,row['asset_id'],actor,staff=staff,ready=True,locked=True)
            except HTTPException as error:
                if error.status_code in (404,409):continue
                raise
            if asset.get('library_book_id')!=book_id:continue
            result['resources'].append({'kind':'LIBRARY_DOCUMENT','asset_type':asset['asset_type'],
                'asset_id':asset['asset_id'],
                'href':f"/libraries/{library_id}/resources/{asset['asset_id']}"})
        # Recheck current membership while still under the authority barrier.
        assets.fresh_guard(library_id,actor,staff=staff,locked=True)
        if result['resources']:
            result.update(status='AUTHORIZED',resource_link_present=True,asset_present=True,
                          access_authorized=True,full_text_accessible=True)
        return result


def global_status(work_id, actor):
    from backend.services.book_capability_service import books_collection, authorize_reader
    from backend.institution_dependencies import actor_id
    from rag.book_assets import valid_work_id, readable_path
    if not valid_work_id(work_id) or not books_collection.find_one({'work_id':work_id},{'_id':1}):
        raise HTTPException(404,'Book not found.')
    result=unknown(work_id)
    try:
        authorize_reader(actor_id(actor),work_id)
    except HTTPException as error:
        if error.status_code in (403,404):return result
        raise
    if readable_path(work_id) is not None:
        result.update(status='AUTHORIZED',resource_link_present=True,asset_present=True,
            access_authorized=True,full_text_accessible=True,
            resources=[{'kind':'GLOBAL_TEXT','asset_type':'TEXT','asset_id':None,'href':f'/book/{work_id}/read'}])
    return result
