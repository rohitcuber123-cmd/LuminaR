"""Strict tenant circulation commands. Caller identities always come from JWT."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictInt
from backend.schemas.library_catalogue import StrictModel


class Command(StrictModel):
    idempotency_key: UUID


class Borrow(Command):
    library_book_id: UUID


class Review(Command):
    reason: str | None = Field(default=None, max_length=500)


class Renew(Command):
    expected_due_at: datetime


class Stock(Command):
    total_copies: StrictInt = Field(ge=0, le=1000000)
    unavailable_stock: StrictInt = Field(default=0, ge=0, le=1000000)
    circulation_status: Literal['CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE', 'WITHDRAWN'] = 'CIRCULATING'
    allocation_mode: Literal['AGGREGATE', 'COPY'] = 'AGGREGATE'


class Shelf(Command):
    shelf_location: str | None = Field(default=None, max_length=200)
    call_number: str | None = Field(default=None, max_length=100)


class CopyCondition(Command):
    status: Literal['AVAILABLE', 'LOST', 'DAMAGED', 'WITHDRAWN']

