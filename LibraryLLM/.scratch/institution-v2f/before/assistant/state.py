"""Bounded user-owned TTL state. Single-process foundation, never raw chat history."""
import asyncio
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from fastapi import HTTPException

from assistant.schemas import Filters, Intent, PendingAction, RecommendationMode


@dataclass
class ResultContext:
    """Bounded canonical IDs and validated parameters, never raw chat history."""
    intent: Intent
    query: str | None = None
    filters: Filters = field(default_factory=Filters)
    page_size: int = 10
    seed_work_ids: list[str] = field(default_factory=list)
    mode: RecommendationMode | None = None
    candidate_work_ids: list[str] = field(default_factory=list)
    delivered_work_ids: list[str] = field(default_factory=list)
    next_offset: int = 0
    has_more: bool = False
    candidate_depth: int = 0
    exhausted: bool = True


@dataclass
class Conversation:
    conversation_id: str
    owner: str
    touched: float = field(default_factory=monotonic)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    recent_result_work_ids: list[str] = field(default_factory=list)
    # None means no result source has been established; [] is an explicit
    # empty active list and must not fall back to older comparison/page IDs.
    active_result_work_ids: list[str] | None = None
    selected_work_ids: list[str] = field(default_factory=list)
    last_search_work_ids: list[str] = field(default_factory=list)
    last_recommendation_work_ids: list[str] = field(default_factory=list)
    last_recommendation_seed_work_ids: list[str] = field(default_factory=list)
    last_recommendation_mode: RecommendationMode | None = None
    last_comparison_work_ids: list[str] = field(default_factory=list)
    last_comparison_fields: list[str] = field(default_factory=list)
    last_reading_list_work_ids: list[str] = field(default_factory=list)
    result_context: ResultContext | None = None
    last_referenced_work_ids: list[str] = field(default_factory=list)
    last_intent: Intent | None = None
    # Two compact resolved turns, never transcripts or model reasoning.
    semantic_turns: list[dict] = field(default_factory=list)
    awaiting_criteria: bool = False
    last_result_type: str | None = None
    pending: PendingAction | None = None
    pending_issue_id: int | None = None
    pending_deadline: float = 0


class ConversationStore:
    def __init__(self, ttl=1800, max_entries=1000):
        self.ttl, self.max_entries = ttl, max_entries
        self.entries: dict[str, Conversation] = {}

    def get(self, conversation_id, owner):
        now = monotonic()
        for key, value in list(self.entries.items()):
            if not value.lock.locked() and now - value.touched > self.ttl:
                del self.entries[key]
        if conversation_id:
            state = self.entries.get(conversation_id)
            if state is None or state.owner != owner:
                raise HTTPException(404, 'Conversation not found or expired.')
        else:
            if len(self.entries) >= self.max_entries:
                idle = [s for s in self.entries.values() if not s.lock.locked()]
                if not idle:
                    raise HTTPException(503, 'Assistant conversations are busy.')
                del self.entries[min(idle, key=lambda s: s.touched).conversation_id]
            state = Conversation(uuid4().hex, owner)
            self.entries[state.conversation_id] = state
        state.touched = now
        return state
