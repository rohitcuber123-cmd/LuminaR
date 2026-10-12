"""Strict, secret-safe requests for the additive institution API."""
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator


class Role(str, Enum):
    GENERAL_USER = 'GENERAL_USER'
    LIBRARIAN = 'LIBRARIAN'
    ADMIN = 'ADMIN'


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)


class Address(StrictRequest):
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)


class LibraryProfile(StrictRequest):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    contact_email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: Address | None = None

    @field_validator('name')
    @classmethod
    def trim_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Library name must contain at least two characters.')
        return value


def validate_code(value):
    if value is not None and not 8 <= len(value.get_secret_value()) <= 128:
        raise ValueError('Access code must contain 8 to 128 characters.')
    return value


class AccessRequest(StrictRequest):
    access_mode: str = Field(pattern=r'^(PUBLIC|PRIVATE_CODE)$')
    access_code: SecretStr | None = None

    _code_length = field_validator('access_code')(validate_code)

    @model_validator(mode='after')
    def private_requires_code(self):
        if self.access_mode == 'PRIVATE_CODE' and self.access_code is None:
            raise ValueError('A new access code is required for private access.')
        if self.access_mode == 'PUBLIC' and self.access_code is not None:
            raise ValueError('Public libraries do not use an access code.')
        return self


class RegisterLibrary(LibraryProfile, AccessRequest):
    slug: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$')
    library_type: str = Field(pattern=r'^(PUBLIC_LIBRARY|PRIVATE_INSTITUTION)$')

    @model_validator(mode='after')
    def consistent_type(self):
        expected = 'PUBLIC_LIBRARY' if self.access_mode == 'PUBLIC' else 'PRIVATE_INSTITUTION'
        if self.library_type != expected:
            raise ValueError('Library type must match its access mode.')
        return self


class JoinLibrary(StrictRequest):
    access_code: SecretStr | None = Field(default=None, max_length=128)


class RotateCode(StrictRequest):
    access_code: SecretStr
    _code_length = field_validator('access_code')(validate_code)


class InviteStaff(StrictRequest):
    email: EmailStr
    role: str = Field(pattern=r'^(ADMIN|LIBRARIAN)$')

    @field_validator('email', mode='before')
    @classmethod
    def trim_email(cls, value):
        return value.strip() if isinstance(value, str) else value


class InvitationAction(StrictRequest):
    token: SecretStr | None = Field(default=None, min_length=32, max_length=128)


class MembershipChange(StrictRequest):
    role: Role | None = None
    status: str | None = Field(default=None, pattern=r'^(ACTIVE|SUSPENDED|REMOVED)$')

    @model_validator(mode='after')
    def nonempty(self):
        if self.role is None and self.status is None:
            raise ValueError('Choose a role or status change.')
        return self


LibraryID = UUID
