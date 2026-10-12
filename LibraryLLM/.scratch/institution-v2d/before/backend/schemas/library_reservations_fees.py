"""Part 2C commands: tenant identities are path UUIDs and authenticated actors."""
from typing import Literal
from pydantic import Field, StrictInt, field_validator
from backend.schemas.library_lending import Command, Borrow


class Reservation(Borrow):
    pass


class Reason(Command):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator('reason')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('A reason is required.')
        return value.strip()


class Adjustment(Reason):
    direction: Literal['CHARGE', 'CREDIT']
    amount_minor: StrictInt = Field(gt=0, le=1000000000000)


class Payment(Command):
    amount_minor: StrictInt = Field(gt=0, le=1000000000000)
    method: Literal['CASH', 'EXTERNAL', 'OTHER']
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class Policy(Command):
    overdue_enabled: bool = True
    rate_minor_per_day: StrictInt = Field(default=500, ge=0, le=100000000)
    currency: Literal['INR'] = 'INR'
    grace_days: StrictInt = Field(default=0, ge=0, le=365)
    charge_stop_policy: Literal['PHYSICAL_RECEIPT', 'FIRST_VALID_RETURN_REQUEST'] = 'PHYSICAL_RECEIPT'
