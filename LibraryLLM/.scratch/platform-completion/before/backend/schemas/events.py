"""Events V1 inputs; audit identity/status are always server-controlled."""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, StrictBool, field_validator, model_validator

class Category(str, Enum):
    NEW_ARRIVALS='NEW_ARRIVALS'
    BOOK_SALE='BOOK_SALE'
    WORKSHOP='WORKSHOP'
    AUTHOR_EVENT='AUTHOR_EVENT'
    READING_CLUB='READING_CLUB'
    COMMUNITY_EVENT='COMMUNITY_EVENT'
    LIBRARY_PROGRAM='LIBRARY_PROGRAM'
    LIBRARY_NOTICE='LIBRARY_NOTICE'
    CLOSURE='CLOSURE'
    EXHIBITION='EXHIBITION'
    OTHER='OTHER'

class Status(str, Enum):
    DRAFT='DRAFT'
    PUBLISHED='PUBLISHED'
    CANCELLED='CANCELLED'
    ARCHIVED='ARCHIVED'

WorkID = Annotated[str, StringConstraints(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')]

class EventCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title: str=Field(min_length=3,max_length=140)
    category: Category
    summary: str=Field(default='',max_length=300)
    description: str=Field(default='',max_length=5000)
    start_at: datetime | None=None
    end_at: datetime | None=None
    location: str | None=Field(default=None,max_length=200)
    featured: StrictBool=False
    related_work_ids: list[WorkID]=Field(default_factory=list,max_length=12)

    @field_validator('start_at','end_at')
    @classmethod
    def utc(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('Use a timezone-aware date and time.')
            return value.astimezone(timezone.utc)
        return value

    @field_validator('related_work_ids')
    @classmethod
    def unique(cls, values):
        if len(values)!=len(set(values)):
            raise ValueError('Related book IDs must not be repeated.')
        return values

    @model_validator(mode='after')
    def dates(self):
        if self.end_at and not self.start_at:
            raise ValueError('Provide a start time before setting an end time.')
        if self.start_at and self.end_at and self.end_at<self.start_at:
            raise ValueError('End time cannot be before start time.')
        return self

class EventPatch(EventCreate):
    title: str | None=Field(default=None,min_length=3,max_length=140)
    category: Category | None=None
    summary: str | None=Field(default=None,max_length=300)
    description: str | None=Field(default=None,max_length=5000)
    featured: StrictBool | None=None
    related_work_ids: list[WorkID] | None=Field(default=None,max_length=12)

    @field_validator('related_work_ids')
    @classmethod
    def unique(cls, values):
        return EventCreate.unique(values) if values is not None else None

    @model_validator(mode='after')
    def dates(self):
        # The complete merged document is validated by the service.
        return self

class SeenRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    cursor: str=Field(min_length=1,max_length=40000)
