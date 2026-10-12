"""Exact catalogue entity lookup for the assistant, without ranking new candidates."""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.dependencies import get_current_user
from backend.database.mongodb import books_collection
from backend.services.availability_service import with_authoritative_availability

router = APIRouter(prefix='/assistant/catalogue', tags=['Assistant catalogue'])


class EntityRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, min_length=1, max_length=250)
    author: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def nonempty(self):
        if not (self.title or '').strip() and not (self.author or '').strip():
            raise ValueError('Provide a title or author.')
        return self


@router.post('/resolve')
def resolve(request: EntityRequest, current_user=Depends(get_current_user)):
    query = {}
    if request.title:
        query['title'] = {'$regex': '^' + re.escape(request.title.strip()) + '$', '$options': 'i'}
    if request.author:
        query['authors'] = {'$regex': re.escape(request.author.strip()), '$options': 'i'}
    rows = list(books_collection.find(query, {'_id': 0}).limit(6))
    return {'books': [with_authoritative_availability(row) for row in rows],
            'truncated': len(rows) == 6}
