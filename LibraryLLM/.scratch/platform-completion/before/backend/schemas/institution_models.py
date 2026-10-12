"""Persisted Institution V1 contracts; account IDs remain canonical integers."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from backend.schemas.institutions import Address, Role


class StoredModel(BaseModel):
    model_config = ConfigDict(extra='ignore')


class Library(StoredModel):
    library_id: UUID
    name: str
    slug: str
    slug_normalized: str
    description: str | None = None
    library_type: Literal['PUBLIC_LIBRARY', 'PRIVATE_INSTITUTION']
    access_mode: Literal['PUBLIC', 'PRIVATE_CODE']
    owner_user_id: int
    contact_email: str | None = None
    phone: str | None = None
    address: Address | None = None
    status: Literal['PROVISIONING', 'ACTIVE', 'SUSPENDED', 'ARCHIVED']
    created_at: datetime
    updated_at: datetime


class LibraryMembership(StoredModel):
    membership_id: UUID
    library_id: UUID
    user_id: int
    role: Role
    status: Literal['ACTIVE', 'SUSPENDED', 'REMOVED']
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int | None = None
    role_changed_by_user_id: int | None = None
    suspended_by_user_id: int | None = None
    removed_by_user_id: int | None = None
    grant_invitation_id: UUID | None = None


class LibraryInvitation(StoredModel):
    invitation_id: UUID
    library_id: UUID
    email_normalized: str
    role: Literal['ADMIN', 'LIBRARIAN']
    invited_user_id: int | None = None
    invited_by_user_id: int
    status: Literal['PENDING', 'ACCEPTED', 'DECLINED', 'REVOKED', 'EXPIRED']
    token_hash: str | None = None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
    accepted_by_user_id: int | None = None
    revoked_at: datetime | None = None
    revoked_by_user_id: int | None = None


class LibraryAuditEvent(StoredModel):
    event_id: str
    library_id: UUID
    event: str
    actor_user_id: int
    target_user_id: int | None = None
    target_email_normalized: str | None = None
    membership_id: UUID | None = None
    metadata: dict = {}
    created_at: datetime
