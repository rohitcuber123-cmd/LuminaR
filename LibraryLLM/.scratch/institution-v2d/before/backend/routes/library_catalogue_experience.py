from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Path
from pydantic import BaseModel, Field
from backend.dependencies import get_current_user
from backend.services import library_catalogue_experience as service

router = APIRouter(prefix='/libraries/{library_id}/catalogue', tags=['Library catalogue experience'])


@router.get('/source')
def source(library_id: UUID, actor=Depends(get_current_user)):
    return service.source(str(library_id), actor)


@router.get('/home')
def home(library_id: UUID, actor=Depends(get_current_user)):
    return service.home(str(library_id), actor)


class RecommendationCandidates(BaseModel):
    work_ids: list[str] = Field(default_factory=list, max_length=200)
    limit: int = Field(default=10, ge=1, le=50)


@router.post('/recommendations')
def recommendations(library_id: UUID, body: RecommendationCandidates, actor=Depends(get_current_user)):
    # Read-only candidate scoping. No recommendation training, feedback or global writes.
    return service.recommendations(str(library_id), actor, body.work_ids, body.limit)


@router.get('/books')
def books(library_id: UUID, search: str = Query('', max_length=150), subject: str = Query('', max_length=200),
          author: str = Query('', max_length=150), circulation_status: Literal['', 'CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE'] = '',
          sort: Literal['title', 'new_arrivals', 'popular'] = 'title', offset: int = Query(0, ge=0, le=100000),
          limit: int = Query(20, ge=1, le=50), actor=Depends(get_current_user)):
    return service.books(str(library_id), actor, search=search, subject=subject, author=author,
        circulation_status=circulation_status, sort=sort, offset=offset, limit=limit)


@router.get('/genres')
def genres(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(50, ge=1, le=100), actor=Depends(get_current_user)):
    return service.genres(str(library_id), actor, offset, limit)


@router.get('/books/{library_book_id}')
def detail(library_id: UUID, library_book_id: UUID, actor=Depends(get_current_user)):
    return service.detail(str(library_id), str(library_book_id), actor)


@router.get('/global-books/{work_id}')
def global_context(library_id: UUID, work_id: str = Path(pattern=r'^OL\d+W$', max_length=100), actor=Depends(get_current_user)):
    return service.global_context(str(library_id), work_id, actor)
