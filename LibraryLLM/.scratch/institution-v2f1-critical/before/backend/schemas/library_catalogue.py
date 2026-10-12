"""Institution-owned metadata. ISBN/work identity is always optional."""
from datetime import date, datetime, timezone
import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


def normalize_title(value):
    if not isinstance(value, str):
        raise ValueError('Title is required.')
    value = value.strip()
    if not value:
        raise ValueError('Title is required.')
    return value


def normalize_values(value):
    if isinstance(value, str):
        value = re.split(r'[;|]', value)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError('Use a list of text values.')
    return list(dict.fromkeys(v.strip() for v in value if v.strip()))


def validate_subjects(value):
    values = normalize_values(value)
    if not values or any(len(v) > 200 for v in values):
        raise ValueError('At least one meaningful Subject / Genre is required; each value must be at most 200 characters.')
    return values


def normalize_isbn(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValueError('ISBN must be text.')
    number = re.sub(r'[\s-]', '', value).upper()
    if re.fullmatch(r'[0-9]{9}[0-9X]', number):
        if sum((10-i) * (10 if digit == 'X' else int(digit)) for i, digit in enumerate(number)) % 11 == 0:
            return number
    elif re.fullmatch(r'97[89][0-9]{10}', number):
        if sum(int(digit) * (1 if i % 2 == 0 else 3) for i, digit in enumerate(number)) % 10 == 0:
            return number
    raise ValueError('ISBN has an invalid format or check digit.')


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Metadata(StrictModel):
    isbn: str | None = Field(default=None, max_length=40)
    isbn_10: str | None = Field(default=None, max_length=40)
    isbn_13: str | None = Field(default=None, max_length=40)
    authors: list[str] = Field(default_factory=list, max_length=25)
    publisher: str | None = Field(default=None, max_length=300)
    publication_year: StrictInt | None = Field(default=None, ge=1, le=datetime.now(timezone.utc).year + 1)
    edition: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    local_call_number: str | None = Field(default=None, max_length=100)
    shelf_location: str | None = Field(default=None, max_length=200)
    local_tags: list[str] = Field(default_factory=list, max_length=30)
    acquisition_note: str | None = Field(default=None, max_length=1000)

    @field_validator('isbn', 'isbn_10', 'isbn_13')
    @classmethod
    def isbn_value(cls, value, info):
        value = normalize_isbn(value)
        length = {'isbn_10': 10, 'isbn_13': 13}.get(info.field_name)
        if value and length and len(value) != length:
            raise ValueError('ISBN length does not match its field.')
        return value

    @field_validator('authors', 'local_tags', mode='before')
    @classmethod
    def lists(cls, value):
        values = normalize_values(value)
        if any(len(v) > 300 for v in values):
            raise ValueError('A metadata value is too long.')
        return values

    @field_validator('publisher', 'edition', 'language', 'description', 'local_call_number', 'shelf_location', 'acquisition_note')
    @classmethod
    def optional_text(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode='after')
    def consistent_isbn(self):
        values = [v for v in (self.isbn, self.isbn_10, self.isbn_13) if v]
        tens, thirteens = {v for v in values if len(v) == 10}, {v for v in values if len(v) == 13}
        if len(tens) > 1 or len(thirteens) > 1:
            raise ValueError('Conflicting ISBN values.')
        if tens and thirteens:
            base = '978' + next(iter(tens))[:9]
            converted = base + str((-sum(int(v) * (1 if i % 2 == 0 else 3) for i, v in enumerate(base))) % 10)
            if converted not in thirteens:
                raise ValueError('ISBN-10 and ISBN-13 refer to different editions.')
        return self


class BookCreate(Metadata):
    idempotency_key: UUID | None = None
    circulation_status: Literal['CIRCULATING', 'REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE', 'WITHDRAWN'] = 'CIRCULATING'
    title: str = Field(min_length=1, max_length=500)
    subjects: list[str] = Field(min_length=1, max_length=30)
    global_work_id: str | None = Field(default=None, min_length=1, max_length=100)
    copies: StrictInt = Field(default=1, ge=0, le=1000000)
    available_copies: StrictInt | None = Field(default=None, ge=0, le=1000000)
    barcode: str | None = Field(default=None, min_length=1, max_length=128)

    _title = field_validator('title')(normalize_title)

    @field_validator('subjects', mode='before')
    @classmethod
    def subjects_value(cls, value):
        return validate_subjects(value)

    @field_validator('global_work_id', 'barcode')
    @classmethod
    def identifier(cls, value):
        if value is not None and not value.strip():
            raise ValueError('Identifier cannot be blank.')
        return value.strip() if value else None

    @model_validator(mode='after')
    def quantity(self):
        if self.available_copies is not None and self.available_copies > self.copies:
            raise ValueError('Available inventory snapshot cannot exceed total copies.')
        if self.barcode and self.copies < 1:
            raise ValueError('A known copy needs a positive holding quantity.')
        return self


class BookUpdate(Metadata):
    idempotency_key: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    subjects: list[str] | None = Field(default=None, min_length=1, max_length=30)
    _title = field_validator('title')(normalize_title)
    _subjects = field_validator('subjects', mode='before')(validate_subjects)


class HoldingUpdate(StrictModel):
    total_copies: StrictInt = Field(ge=0, le=1000000)
    available_copies: StrictInt = Field(ge=0, le=1000000)
    @model_validator(mode='after')
    def quantity(self):
        if self.available_copies > self.total_copies:
            raise ValueError('Available inventory snapshot cannot exceed total copies.')
        return self


class LinkGlobal(StrictModel):
    idempotency_key: UUID | None = None
    global_work_id: str | None = Field(default=None, min_length=1, max_length=100)


class CopyCreate(StrictModel):
    idempotency_key: UUID | None = None
    barcode: str | None = Field(default=None, min_length=1, max_length=128)
    status: Literal['AVAILABLE', 'LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED'] = 'AVAILABLE'
    acquisition_date: date | None = None


class ImportApply(StrictModel):
    existing_policy: Literal['skip', 'increase_quantity'] = 'skip'


BOOK_FIELDS = ('title', 'subjects', 'authors', 'publisher', 'publication_year', 'edition', 'language', 'description',
               'isbn_10', 'isbn_13', 'local_call_number', 'shelf_location', 'local_tags', 'acquisition_note')


def book_payload(request):
    data = request.model_dump()
    isbn = data.pop('isbn', None)
    if isbn:
        data['isbn_10' if len(isbn) == 10 else 'isbn_13'] = isbn
    return data


# Persisted contracts supplement the tenant-required repository and route guards.
from uuid import UUID


class LibraryBookRecord(Metadata):
    model_config = ConfigDict(extra='ignore')
    library_book_id: UUID
    library_id: UUID
    accession_number: str
    accession_sequence: StrictInt = Field(ge=1)
    global_work_id: str | None = None
    title: str
    subjects: list[str]
    source: Literal['MANUAL', 'DATASET_IMPORT', 'LEGACY_MIGRATION', 'GLOBAL_CATALOGUE_LINK']
    status: Literal['PROVISIONING', 'ACTIVE', 'WITHDRAWN']
    needs_review: bool = False
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int
    updated_by_user_id: int


class LibraryHolding(StrictModel):
    model_config = ConfigDict(extra='ignore')
    holding_id: UUID
    library_id: UUID
    library_book_id: UUID
    total_copies: StrictInt = Field(ge=0)
    available_copies: StrictInt = Field(ge=0)
    shelf_location: str | None = None
    call_number: str | None = None
    local_tags: list[str] = Field(default_factory=list)
    acquisition_note: str | None = None
    quantity_semantics: Literal['INVENTORY_SNAPSHOT_NOT_CIRCULATION']
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int
    updated_by_user_id: int

    @model_validator(mode='after')
    def quantities(self):
        if self.available_copies > self.total_copies:
            raise ValueError('Available inventory snapshot cannot exceed total copies.')
        return self


class LibraryCopy(StrictModel):
    model_config = ConfigDict(extra='ignore')
    copy_id: UUID
    library_id: UUID
    library_book_id: UUID
    holding_id: UUID
    copy_number: StrictInt = Field(ge=1)
    barcode: str | None = None
    status: Literal['AVAILABLE', 'HELD_FOR_REQUEST', 'BORROWED', 'RESERVED', 'LOST', 'DAMAGED', 'WITHDRAWN', 'UNVERIFIED']
    acquisition_date: date | None = None
    created_at: datetime
    updated_at: datetime
