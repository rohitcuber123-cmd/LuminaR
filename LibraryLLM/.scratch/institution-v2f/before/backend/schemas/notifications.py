"""Canonical notification tenancy, independent of catalogue work identity."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class NotificationScope(BaseModel):
    user_id: int = Field(gt=0)
    scope: Literal['GLOBAL', 'PLATFORM', 'LIBRARY']
    library_id: UUID | None = None

    @model_validator(mode='after')
    def tenancy(self):
        if (self.scope == 'LIBRARY') != (self.library_id is not None):
            raise ValueError('Only library notifications require a canonical library UUID.')
        return self
