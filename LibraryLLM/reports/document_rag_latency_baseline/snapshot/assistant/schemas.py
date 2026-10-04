from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from assistant.profiling import timed

WorkID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                         max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]


class Intent(str, Enum):
    SEARCH_BOOKS = 'SEARCH_BOOKS'
    RECOMMEND_BOOKS = 'RECOMMEND_BOOKS'
    RECOMMEND_FROM_BOOK = 'RECOMMEND_FROM_BOOK'
    RECOMMEND_FROM_SELECTION = 'RECOMMEND_FROM_SELECTION'
    COMPARE_BOOKS = 'COMPARE_BOOKS'
    CHECK_AVAILABILITY = 'CHECK_AVAILABILITY'
    BOOK_DETAILS = 'BOOK_DETAILS'
    BORROW_BOOK = 'BORROW_BOOK'
    RETURN_BOOK = 'RETURN_BOOK'
    RESERVE_BOOK = 'RESERVE_BOOK'
    USER_LOANS = 'USER_LOANS'
    USER_RESERVATIONS = 'USER_RESERVATIONS'
    USER_HISTORY = 'USER_HISTORY'
    USER_FEES = 'USER_FEES'
    # Reading list (Phase 3)
    USER_READING_LIST = 'USER_READING_LIST'
    ADD_TO_READING_LIST = 'ADD_TO_READING_LIST'
    REMOVE_FROM_READING_LIST = 'REMOVE_FROM_READING_LIST'
    CLEAR_READING_LIST = 'CLEAR_READING_LIST'
    # Available alternatives (Phase 5/6)
    RECOMMEND_AVAILABLE_SIMILAR = 'RECOMMEND_AVAILABLE_SIMILAR'
    GENERAL_LIBRARY_HELP = 'GENERAL_LIBRARY_HELP'
    BOOK_CONTENT_QUESTION = 'BOOK_CONTENT_QUESTION'
    DOCUMENT_QUESTION = 'DOCUMENT_QUESTION'
    CLARIFICATION = 'CLARIFICATION'
    UNKNOWN = 'UNKNOWN'


class AssistantAction(str, Enum):
    RECOMMEND = 'RECOMMEND'
    AVAILABLE_NOW = 'AVAILABLE_NOW'
    VIEW_BOOK = 'VIEW_BOOK'
    SELECT_BOOK = 'SELECT_BOOK'
    UNSELECT_BOOK = 'UNSELECT_BOOK'
    COMPARE = 'COMPARE'
    RECOMMEND_SIMILAR = 'RECOMMEND_SIMILAR'
    RECOMMEND_FROM_SELECTION = 'RECOMMEND_FROM_SELECTION'
    RECOMMEND_AVAILABLE_SIMILAR = 'RECOMMEND_AVAILABLE_SIMILAR'
    CHECK_AVAILABILITY = 'CHECK_AVAILABILITY'
    BORROW = 'BORROW'
    RESERVE = 'RESERVE'
    RETURN = 'RETURN'
    CONFIRM_ACTION = 'CONFIRM_ACTION'
    CANCEL_ACTION = 'CANCEL_ACTION'
    ADD_TO_READING_LIST = 'ADD_TO_READING_LIST'
    REMOVE_FROM_READING_LIST = 'REMOVE_FROM_READING_LIST'
    SHOW_MORE = 'SHOW_MORE'
    EXPLAIN_RECOMMENDATION = 'EXPLAIN_RECOMMENDATION'
    EXPLAIN_COMPARISON = 'EXPLAIN_COMPARISON'


class RecommendationMode(str, Enum):
    PERSONALIZED_EXISTING_FORMULA = 'PERSONALIZED_EXISTING_FORMULA'
    SINGLE_SELECTED_BOOK = 'SINGLE_SELECTED_BOOK'
    MULTI_SELECTED_BOOKS = 'MULTI_SELECTED_BOOKS'
    EXPLICIT_BOOK_SEED = 'EXPLICIT_BOOK_SEED'


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Filters(StrictModel):
    available_only: bool = False
    author: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    exclude_seed_authors: bool = False
    sort_preference: Literal['relevance', 'title', 'rating'] = 'relevance'


class AssistantIntent(StrictModel):
    intent: Intent
    confidence: float = Field(default=0.0, ge=0, le=1)
    query: str | None = Field(default=None, max_length=2000)
    mentioned_titles: list[str] = Field(default_factory=list, max_length=4)
    mentioned_authors: list[str] = Field(default_factory=list, max_length=4)
    resolved_work_ids: list[WorkID] = Field(default_factory=list, max_length=4)
    requested_result_count: int = Field(default=10, ge=1, le=20)
    filters: Filters = Field(default_factory=Filters)
    comparison_fields: list[str] = Field(default_factory=list, max_length=12)
    ordinal_references: list[int] = Field(default_factory=list, max_length=4)
    reference: Literal['none', 'this', 'these', 'previous_recommendation'] = 'none'
    requires_confirmation: bool = False
    clarification_needed: bool = False
    unsupported_filters: list[str] = Field(default_factory=list, max_length=10)


class PageContext(StrictModel):
    work_id: WorkID | None = None
    work_ids: list[WorkID] = Field(default_factory=list, max_length=4)
    document_id: str | None = Field(default=None, min_length=1, max_length=128)


class AssistantRequest(StrictModel):
    @model_validator(mode='wrap')
    @classmethod
    def profile_validation(cls, value, handler):
        with timed('request_validation'):
            return handler(value)

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=64)
    selected_work_ids: list[WorkID] = Field(default_factory=list, max_length=4)
    recent_work_ids: list[WorkID] = Field(default_factory=list, max_length=20)
    page_context: PageContext = Field(default_factory=PageContext)
    pending_action_id: str | None = Field(default=None, min_length=1, max_length=64)
    action: Literal['CONFIRM_ACTION', 'CANCEL_ACTION', 'COMPARE', 'RECOMMEND',
                    'RECOMMEND_SIMILAR', 'RECOMMEND_FROM_SELECTION', 'CHECK_AVAILABILITY',
                    'AVAILABLE_NOW', 'USER_LOANS', 'USER_FEES', 'USER_RESERVATIONS',
                    'BOOK_CONTENT_QUESTION', 'DOCUMENT_QUESTION',
                    'USER_READING_LIST', 'ADD_TO_READING_LIST', 'REMOVE_FROM_READING_LIST',
                    'CLEAR_READING_LIST', 'RECOMMEND_AVAILABLE_SIMILAR',
                    'EXPLAIN_RECOMMENDATION', 'EXPLAIN_COMPARISON', 'SHOW_MORE'] | None = None
    # Pagination: offset for show-more continuation
    result_offset: int = Field(default=0, ge=0, le=200)


class Book(BaseModel):
    """Only fields returned by the catalogue, with absent values kept null."""
    work_id: WorkID
    title: str | None = None
    authors: str | list[str] | None = None
    subjects: str | list[str] | None = None
    description: str | None = None
    average_rating: float | None = None
    available_copies: int | None = None
    total_copies: int | None = None
    shelf_location: str | None = None


class Availability(StrictModel):
    work_id: WorkID
    available: bool | None = None
    available_copies: int | None = None
    total_copies: int | None = None


class Action(StrictModel):
    type: AssistantAction
    work_id: WorkID | None = None
    action_id: str | None = None


class PendingAction(StrictModel):
    action_id: str
    type: Intent
    work_id: WorkID
    requires_confirmation: bool = True
    expires_at: str
    enabled: bool = False


class AssistantError(StrictModel):
    code: str
    service: str
    message: str


class Clarification(StrictModel):
    reason: str
    choices: list[Book] = Field(default_factory=list)


class Comparison(StrictModel):
    books: list[Book]
    requested_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class AssistantResponse(StrictModel):
    conversation_id: str
    intent: Intent = Intent.UNKNOWN
    message: str = ''
    books: list[Book] = Field(default_factory=list)
    comparison: Comparison | None = None
    recommendation_mode: RecommendationMode | None = None
    seed_work_ids: list[WorkID] = Field(default_factory=list)
    availability: list[Availability] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    clarification: Clarification | None = None
    pending_action: PendingAction | None = None
    account: dict[str, Any] | None = None
    reading_list: list[Book] | None = None
    rag: dict[str, Any] | None = None
    errors: list[AssistantError] = Field(default_factory=list)
    # Pagination metadata (show-more)
    has_more: bool = False
    result_offset: int = 0
    # Explanation availability signals (Phase 7/8)
    explanation_available: bool = False
