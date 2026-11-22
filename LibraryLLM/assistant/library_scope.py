"""Request-local tenant adapters over existing authorized catalogue services.

No candidate metadata reaches the model until Core projects canonical holdings.
"""
import asyncio
from uuid import UUID
from fastapi import HTTPException
from assistant.schemas import Book
from assistant.tools import ServiceTransport, ToolFailure, AssistantReadingListTool


class LibraryTransport:
    def __init__(self, transport, library_id, staff=False):
        self.raw, self.library_id, self.staff = transport, library_id, staff

    async def call(self, service, method, path, **kwargs):
        scoped_core=service=='core' and path.startswith(f'/libraries/{self.library_id}/')
        scoped_search=service=='search' and method=='GET' and path==f'/libraries/{self.library_id}/catalogue/search'
        if not (scoped_core or scoped_search):
            raise ToolFailure('core', 'SCOPED_TOOL_UNAVAILABLE', 'This action is not supported in this library context.')
        if self.staff and '/catalogue/' in path:
            kwargs['params']={**kwargs.get('params',{}),'staff':True}
        return await self.raw.call(service, method, path, **kwargs)


class LibraryCatalogue:
    def __init__(self, transport, library_id):
        self.transport, self.library_id = transport, library_id
        self.base = f'/libraries/{library_id}/catalogue'

    def project(self, row):
        if not row or row.get('library_id') != self.library_id or row.get('source') != 'LIBRARY' or row.get('owned_by_current_library') is not True:
            raise ToolFailure('core', 'BOOK_NOT_IN_LIBRARY', 'Book not found in this library.')
        identity = str(UUID(row['library_book_id']))
        stock = row.get('availability') or {}
        return Book(work_id=identity, library_id=self.library_id, library_book_id=identity,
                    global_work_id=row.get('global_work_id'), title=row.get('title'), authors=row.get('authors'),
                    subjects=row.get('subjects'), description=row.get('description'),
                    average_rating=row.get('average_rating'),rating_count=row.get('rating_count'),
                    available_copies=stock.get('requestable'), total_copies=stock.get('total'),
                    shelf_location=row.get('shelf_location'))

    async def book(self, identity):
        try:
            canonical = str(UUID(identity))
        except ValueError:
            if not identity.startswith('OL') or not identity.endswith('W') or not identity[2:-1].isdigit():
                raise ToolFailure('core', 'BOOK_NOT_IN_LIBRARY', 'Book not found in this library.')
            result = await self.transport.call('core', 'GET', f'{self.base}/global-books/{identity}')
        else:
            result = await self.transport.call('core', 'GET', f'{self.base}/books/{canonical}')
        return self.project(result.get('book'))

    async def books(self, identities):
        # Canonical catalogue reads take a per-library fail-closed lock. Parallel
        # lookups from one turn can therefore reject each other and leave work
        # running while the final membership check starts. Preserve order and
        # validate each book through Core, with one overall deadline.
        async def fetch():
            return [await self.book(identity) for identity in dict.fromkeys(identities)]
        try:
            return await asyncio.wait_for(fetch(),40)
        except TimeoutError as error:
            raise ToolFailure('core','CATALOGUE_TIMEOUT','Library catalogue lookup timed out.') from error

    async def resolve(self, title, author):
        result = await self.transport.call('core', 'GET', f'{self.base}/books',
            params={'search':title or '', 'author':author or '', 'limit':6})
        return [self.project(row) for row in result.get('results', [])]


class LibrarySearch:
    def __init__(self, catalogue):self.catalogue = catalogue

    async def search(self, query, count):
        c = self.catalogue
        params={'search':query[:150],'limit':min(count,50),'personalized':False}
        try:
            result=await c.transport.call('search','GET',f'{c.base}/search',params=params)
        except ToolFailure as error:
            if error.error.code in ['HTTP_400','HTTP_401','HTTP_403','HTTP_404','HTTP_409','HTTP_422']:raise
            result=await c.transport.call('core','GET',f'{c.base}/discovery',params=params)
        return [c.project(row).work_id for row in result.get('results', [])]


class LibraryRecommendations:
    def __init__(self, catalogue, raw):self.catalogue, self.raw = catalogue, raw

    async def recommend(self, count, seed=None):
        c = self.catalogue
        seed_book=await c.book(seed) if seed else None
        anchor=seed_book.global_work_id if seed_book else None
        if seed_book and not anchor:
            # Similarity for a local-only seed uses its actual subjects through
            # existing authorized search; never imply a global seed score.
            topics=' '.join(seed_book.subjects) if isinstance(seed_book.subjects,list) else seed_book.subjects or ''
            if not topics.strip():return []
            ids=await LibrarySearch(c).search(topics,50)
            return [identity for identity in ids if identity!=seed_book.work_id][:min(count,50)]
        candidates = []
        try:
            if anchor:
                result = await self.raw.call('recommendation','POST','/recommendations/from-book',json={'work_id':anchor,'limit':50},timeout=8)
            else:
                result = await self.raw.call('recommendation','GET','/recommendations',params={'limit':50,'offset':0},timeout=8)
            candidates = [row['work_id'] for row in result.get('recommendations',[]) if row.get('work_id')][:50]
        except ToolFailure:
            pass  # Existing canonical local-acquisition supplement remains available.
        result = await c.transport.call('core','POST',f'{c.base}/recommendations',json={'work_ids':candidates,'limit':min(count,50)})
        return [c.project(row).work_id for row in result.get('results',[])]


class LibraryReadingList(AssistantReadingListTool):
    def __init__(self,catalogue,raw):self.catalogue,self.raw=catalogue,raw

    async def get(self):
        c=self.catalogue
        result=await c.transport.call('core','GET',f'{c.base}/assistant-reading-list')
        return {'items':[c.project(row).model_dump() for row in result.get('results',[])],'has_more':result.get('has_more',False)}

    async def key(self,identity):
        book=await self.catalogue.book(identity)
        return book.global_work_id or f'local:{book.library_id}:{book.library_book_id}'

    async def add(self,identity):
        return await self.raw.call('core','POST','/reading-list/',json={'work_id':await self.key(identity)})

    async def remove(self,identity):
        return await self.raw.call('core','DELETE',f'/reading-list/{await self.key(identity)}')


class LibraryGraph:
    def __init__(self,catalogue):self.catalogue=catalogue

    async def more_like_this(self,identity,count=10):
        c=self.catalogue;seed=await c.book(identity)
        result=await c.transport.call('core','GET',f'/libraries/{c.library_id}/intelligence/graph',
            params={'limit':100,'staff':getattr(c.transport,'staff',False)})
        if result.get('library_id')!=c.library_id:
            raise ToolFailure('core','INVALID_GRAPH_SCOPE','Library graph unavailable.')
        if result.get('status')!='READY':
            raise ToolFailure('core','TENANT_GRAPH_UNAVAILABLE','This library graph is not ready. Catalogue recommendations remain available.')
        nodes={n['id']:n for n in result.get('nodes',[]) if n.get('type')=='Book'}
        source=next((n['id'] for n in nodes.values() if n.get('library_book_id')==seed.work_id),None)
        neighbors={e['target'] for e in result.get('edges',[]) if e['source']==source}
        scores={}
        for edge in result.get('edges',[]):
            if edge['source'] in nodes and edge['source']!=source and edge['target'] in neighbors:
                scores[edge['source']]=scores.get(edge['source'],0)+1
        recommendations=[]
        for node in sorted(scores,key=lambda n:(-scores[n],n))[:min(count,20)]:
            book=await c.book(nodes[node]['library_book_id'])
            recommendations.append({**book.model_dump(),'score':scores[node],'reason_paths':[]})
        return {'seed_work_id':seed.work_id,'seed':seed.model_dump(),'graph_version':result.get('generation_id'),
            'recommendations':recommendations,'source':'TENANT_KG','limited':result.get('limited',False)}


async def bind_library(tools, client, authorization, library_id, *, transport=None):
    raw = transport or ServiceTransport(client, authorization)
    try:
        await raw.call('core','GET',f'/libraries/{library_id}/catalogue/source')
        context = await raw.call('core','GET',f'/libraries/{library_id}/context')
    except ToolFailure as error:
        status=404 if error.error.code in ['HTTP_403','HTTP_404','HTTP_401'] else 503
        raise HTTPException(status,'Library resource unavailable.') from error
    membership = context.get('membership') or {}
    if context.get('library',{}).get('library_id') != library_id or membership.get('library_id') != library_id or membership.get('status') != 'ACTIVE' or membership.get('role') not in ['GENERAL_USER','ADMIN','LIBRARIAN']:
        raise HTTPException(404,'Library resource not found.')
    transport = LibraryTransport(raw, library_id, membership['role'] in ['ADMIN','LIBRARIAN'])
    tools.effective_scope = f'LIBRARY:{library_id}'
    tools.library_role = membership['role']
    tools.catalogue = LibraryCatalogue(transport, library_id)
    tools.search = LibrarySearch(tools.catalogue)
    tools.recommendation = LibraryRecommendations(tools.catalogue, raw)
    tools.kg = LibraryGraph(tools.catalogue)
    tools.reading_list = LibraryReadingList(tools.catalogue,raw)
    # Existing circulation endpoints still perform their original current-role checks.
    for name in ['loans','reservations','fees']:
        adapter=getattr(tools,name,None)
        if adapter is not None:adapter.transport = transport

    if not getattr(tools,'rag',None):return
    original_rag=tools.rag.callback
    async def scoped_rag(message,work_id=None,document_id=None):
        if not document_id or not document_id.startswith(f'library:{library_id}:asset:'):
            raise ToolFailure('rag','SCOPED_DOCUMENT_REQUIRED','Choose an authorized document from this library.')
        return await original_rag(message,work_id=work_id,document_id=document_id)
    tools.rag.callback=scoped_rag
