"""Explicit tenant document ownership; personal uploads keep their existing model."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Visibility = Literal['STAFF_ONLY', 'MEMBERS']
AssetStatus = Literal['UPLOADING', 'PROCESSING', 'READY', 'FAILED', 'DELETING', 'DELETED']


class AssetUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, min_length=1, max_length=200)
    visibility: Visibility | None = None
    library_book_id: UUID | None = None

    @field_validator('title')
    @classmethod
    def readable_title(cls, value):
        if value is not None and (not value.strip() or any(ord(c) < 32 for c in value)):
            raise ValueError('A readable title is required.')
        return value.strip() if value else value


class LibraryDigitalAsset(BaseModel):
    model_config = ConfigDict(extra='ignore')
    asset_id: UUID
    library_id: UUID
    uploaded_by_user_id: int
    asset_type: Literal['PDF', 'TXT', 'DOCX']
    title: str
    original_filename: str
    media_type: Literal['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    byte_size: int
    checksum: str
    storage_key: str
    status: AssetStatus
    visibility: Visibility
    library_book_id: UUID | None = None
    global_work_id: str | None = None
    extraction_status: str
    rag_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by_user_id: int | None = None


class LibraryAssetProcessingJob(BaseModel):
    model_config = ConfigDict(extra='ignore')
    job_id: UUID
    library_id: UUID
    asset_id: UUID
    actor_user_id: int
    state: Literal['QUEUED', 'PROCESSING', 'READY', 'FAILED']
    attempt: int
    error_code: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
