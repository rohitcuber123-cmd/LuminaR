"""Plain-text communication inputs. Ownership and publication history are server-only."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

Category = Literal['GENERAL', 'EVENT', 'LIBRARY_UPDATE', 'IMPORTANT_NOTICE']
Priority = Literal['NORMAL', 'IMPORTANT']
Status = Literal['DRAFT', 'PUBLISHED', 'WITHDRAWN']

class Content(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=3, max_length=140)
    body: str = Field(min_length=1, max_length=5000)
    category: Category = 'GENERAL'
    priority: Priority = 'NORMAL'
    linked_event_id: UUID | None = None
    audience: Literal['ALL_ACTIVE_MEMBERS', 'SPECIFIC_MEMBER'] = 'ALL_ACTIVE_MEMBERS'
    recipient_user_id: StrictInt | None = Field(default=None, gt=0, le=9007199254740991)

    @model_validator(mode='after')
    def recipient_scope(self):
        if (self.audience == 'SPECIFIC_MEMBER') != (self.recipient_user_id is not None):
            raise ValueError('Select one member for SPECIFIC_MEMBER; all-members mode has no selected recipient.')
        return self

    @field_validator('title', 'body')
    @classmethod
    def plain_text(cls, value):
        if any(c in value for c in '<>') or any(ord(c) < 32 and c not in '\n\r\t' for c in value):
            raise ValueError('Use plain text without HTML or control characters.')
        if '-----BEGIN ' in value and 'PRIVATE KEY-----' in value:
            raise ValueError('Credentials must not be included in announcements.')
        return value

class DraftCreate(Content):
    request_id: UUID

class DraftUpdate(Content):
    revision: StrictInt = Field(ge=0)

class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0)
