"""Typed HTTP adapters to existing service routes and the unchanged local RAG route."""
import asyncio
import logging
import os
from time import perf_counter
from typing import Awaitable, Callable

import httpx

from assistant.schemas import AssistantError, Book, Intent
from assistant.profiling import current, measured, timed

LOG = logging.getLogger('luminar.assistant')


class ToolFailure(Exception):
    def __init__(self, service, code='SERVICE_UNAVAILABLE', message=None):
        self.error = AssistantError(service=service, code=code,
                                   message=message or f'{service.capitalize()} cannot be loaded right now.')
        super().__init__(self.error.message)


class ServiceTransport:
    def __init__(self, client: httpx.AsyncClient, authorization: str):
        self.client, self.authorization = client, authorization

    async def call(self, service, method, path, **kwargs):
        base = os.getenv(f'ASSISTANT_{service.upper()}_URL',
                         {'core': 'http://127.0.0.1:8002', 'search': 'http://127.0.0.1:8003',
                          'recommendation': 'http://127.0.0.1:8004'}[service])
        started = perf_counter()
        try:
            result = await self.client.request(method, base.rstrip('/') + path,
                                               headers={'Authorization': self.authorization}, **kwargs)
            if result.status_code >= 400:
                code = f'HTTP_{result.status_code}'
                # Only expected business-rule errors are exposed, never exception traces.
                detail = result.json().get('detail') if result.status_code in (400, 403, 404, 409) else None
                raise ToolFailure(service, code, detail if isinstance(detail, str) else None)
            return result.json()
        except ToolFailure:
            raise
        except httpx.TimeoutException as exc:
            raise ToolFailure(service, 'TIMEOUT', f'{service.capitalize()} timed out. Please retry.') from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ToolFailure(service) from exc
        finally:
            profile = current.get()
            if profile is not None:
                stage = (service if service != 'core' else
                         'core_metadata' if path.startswith(('/books/', '/assistant/catalogue/')) else 'account_service')
                elapsed = (perf_counter()-started)*1000
                profile['stages_ms'][stage] = profile['stages_ms'].get(stage, 0) + elapsed
            LOG.info('tool service=%s method=%s latency_ms=%.1f', service, method,
                     (perf_counter()-started)*1000)


class AssistantSearchTool:
    def __init__(self, transport):
        self.transport = transport

    async def search(self, query: str, count: int) -> list[str]:
        result = await self.transport.call('search', 'POST', '/search',
                                           json={'query': query, 'top_k': count, 'save_history': False})
        return list(dict.fromkeys(row['work_id'] for row in result.get('results', []) if row.get('work_id')))


class AssistantCatalogueTool:
    def __init__(self, transport):
        self.transport = transport

    async def book(self, work_id: str) -> Book:
        from assistant.schemas import WorkID
        from pydantic import TypeAdapter
        try:
            TypeAdapter(WorkID).validate_python(work_id)
        except ValueError as exc:
            raise ToolFailure('core', 'INVALID_WORK_ID', 'Invalid book identifier.') from exc
        row = await self.transport.call('core', 'GET', f'/books/{work_id}')
        try:
            book = Book.model_validate(row)
            if book.work_id != work_id:
                raise ValueError('Mismatched catalogue identifier')
            return book
        except ValueError as exc:
            raise ToolFailure('core', 'INVALID_CATALOGUE_RESULT') from exc

    @measured('core_metadata_wall')
    async def books(self, work_ids: list[str]) -> list[Book]:
        return list(await asyncio.gather(*(self.book(wid) for wid in dict.fromkeys(work_ids))))

    async def resolve(self, title: str | None, author: str | None) -> list[Book]:
        result = await self.transport.call('core', 'POST', '/assistant/catalogue/resolve',
                                           json={'title': title, 'author': author})
        return [Book.model_validate(row) for row in result.get('books', [])]


class AssistantAvailabilityTool:
    def availability(self, book: Book):
        from assistant.schemas import Availability
        with timed('availability'):
            return Availability(work_id=book.work_id, available_copies=book.available_copies,
                                total_copies=book.total_copies,
                                available=book.available_copies > 0 if book.available_copies is not None else None)


class AssistantRecommendationTool:
    def __init__(self, transport):
        self.transport = transport

    async def recommend(self, count: int, seed: str | None = None) -> list[str]:
        if seed is None:
            result = await self.transport.call('recommendation', 'GET', '/recommendations',
                                               params={'limit': count, 'strict_service_errors': 'true'})
        else:
            result = await self.transport.call('recommendation', 'POST', '/recommendations/from-book',
                                               json={'work_id': seed, 'limit': count})
        return list(dict.fromkeys(r['work_id'] for r in result.get('recommendations', []) if r.get('work_id')))


class AssistantLoanTool:
    def __init__(self, transport):
        self.transport = transport

    async def loans(self, history=False):
        result = await self.transport.call('core', 'GET', '/issues/my')
        issues = result.get('issues', [])
        rows = issues if history else [row for row in issues if row.get('status') == 'ISSUED']
        return {'count': len(rows), 'issues': rows}

    async def borrow(self, work_id):
        return await self.transport.call('core', 'POST', '/issues/issue', json={'work_id': work_id})

    async def return_book(self, issue_id):
        return await self.transport.call('core', 'POST', f'/issues/return/{issue_id}')


class AssistantReservationTool:
    def __init__(self, transport):
        self.transport = transport

    async def reservations(self):
        return await self.transport.call('core', 'GET', '/reservations/my')

    async def reserve(self, work_id):
        return await self.transport.call('core', 'POST', '/reservations/', json={'work_id': work_id})


class AssistantFeeTool:
    def __init__(self, transport):
        self.transport = transport

    async def fees(self):
        return await self.transport.call('core', 'GET', '/fines/my')


class AssistantReadingListTool:
    """Proxy for the existing /reading-list/* core routes.

    All operations are authenticated via the existing authorization header.
    work_ids are validated through the AssistantCatalogueTool before
    any mutation to ensure only real catalogue items can be added.
    """
    def __init__(self, transport):
        self.transport = transport

    async def get(self) -> dict:
        return await self.transport.call('core', 'GET', '/reading-list/my')

    async def add(self, work_id: str) -> dict:
        return await self.transport.call('core', 'POST', '/reading-list/',
                                         json={'work_id': work_id})

    async def remove(self, work_id: str) -> dict:
        return await self.transport.call('core', 'DELETE', f'/reading-list/{work_id}')

    async def clear(self, work_ids: list[str]) -> None:
        """Remove all given work_ids. Ignores 404 (already gone)."""
        import asyncio
        async def safe_remove(wid):
            try:
                await self.remove(wid)
            except ToolFailure as exc:
                if 'HTTP_404' not in exc.error.code:
                    raise
        await asyncio.gather(*(safe_remove(w) for w in work_ids))


class AssistantRAGTool:
    def __init__(self, callback: Callable[..., Awaitable[dict]]):
        self.callback = callback

    @measured('rag_routing')
    async def ask(self, message, work_id=None, document_id=None):
        return await self.callback(message, work_id=work_id, document_id=document_id)


class AssistantTools:
    def __init__(self, client, authorization, rag_callback):
        transport = ServiceTransport(client, authorization)
        self.search = AssistantSearchTool(transport)
        self.catalogue = AssistantCatalogueTool(transport)
        self.availability = AssistantAvailabilityTool()
        self.recommendation = AssistantRecommendationTool(transport)
        self.loans = AssistantLoanTool(transport)
        self.reservations = AssistantReservationTool(transport)
        self.fees = AssistantFeeTool(transport)
        self.reading_list = AssistantReadingListTool(transport)
        self.rag = AssistantRAGTool(rag_callback)

