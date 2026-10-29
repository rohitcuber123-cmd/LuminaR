"""Compact extraction interface and deterministic normalization adapter for LuminaR V9.

Designed to eliminate model hallucination of character offsets and invalid enums:
1. CompactProposal: Model proposes ONLY intent, constraint_type, exact source substring, modality, and state.
2. Deterministic Resolver: Resolves exact source substring to unique character spans [start, end].
3. Rejection of Ambiguity: Ambiguous repeated substrings, fabricated substrings, or out-of-bounds numbers are strictly rejected.
4. Constrained Decoding Harness: Uses lmformatenforcer for schema enforcement.
"""
from typing import Literal, List, Optional, Tuple, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
import json, re

class CompactConstraintProposal(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    constraint_type: Literal['author', 'title', 'subject', 'rating', 'year', 'format', 'sort', 'topic', 'unsupported']
    exact_source_substring: str = Field(min_length=1, max_length=200)
    modality: Literal['MANDATORY', 'OPTIONAL', 'NON_OPERATIVE'] = 'MANDATORY'
    state: Literal['SUPPLIED', 'MISSING', 'UNCERTAIN', 'UNSUPPORTED'] = 'SUPPLIED'

class CompactExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    intent: Literal['SEARCH', 'CLARIFY', 'NON_SEARCH']
    proposals: List[CompactConstraintProposal] = Field(max_length=16)

class ResolvedConstraint(BaseModel):
    constraint_type: str
    source_span: Tuple[int, int]
    source_text: str
    modality: str
    state: str
    resolved_operand: Optional[Any] = None

class NormalizationResult(BaseModel):
    is_valid: bool
    rejection_reason: Optional[str] = None
    intent: str
    resolved_constraints: List[ResolvedConstraint] = Field(default_factory=list)

def resolve_unique_substring(query: str, substring: str) -> Optional[Tuple[int, int]]:
    """Resolve an exact substring to a unique (start, end) span in the original query.
    Returns None if 0 matches or multiple ambiguous occurrences are found.
    """
    matches = [m.span() for m in re.finditer(re.escape(substring), query)]
    if len(matches) == 1:
        return matches[0]
    return None

def normalize_compact_proposal(query: str, extraction: CompactExtraction) -> NormalizationResult:
    """Deterministically normalize and validate a compact extraction against the immutable query."""
    if not isinstance(query, str) or len(query) > 500:
        return NormalizationResult(is_valid=False, rejection_reason='Query exceeds 500 characters', intent='NON_SEARCH')

    resolved = []
    for prop in extraction.proposals:
        # Check if substring exists uniquely in query
        span = resolve_unique_substring(query, prop.exact_source_substring)
        if span is None:
            # Check if 0 or multiple
            matches = list(re.finditer(re.escape(prop.exact_source_substring), query))
            if len(matches) == 0:
                return NormalizationResult(
                    is_valid=False,
                    rejection_reason=f'Fabricated substring not in query: {prop.exact_source_substring!r}',
                    intent=extraction.intent
                )
            else:
                return NormalizationResult(
                    is_valid=False,
                    rejection_reason=f'Ambiguous repeated substring in query: {prop.exact_source_substring!r}',
                    intent=extraction.intent
                )

        # Parse numeric operands deterministically if type is rating or year
        parsed_operand = None
        if prop.state == 'SUPPLIED':
            if prop.constraint_type == 'rating':
                num_match = re.search(r'\d+(?:\.\d+)?', prop.exact_source_substring)
                if not num_match:
                    return NormalizationResult(is_valid=False, rejection_reason='Missing numeric value in rating proposal', intent=extraction.intent)
                val = float(num_match.group(0))
                if not (0.0 <= val <= 5.0):
                    return NormalizationResult(is_valid=False, rejection_reason=f'Rating out of bounds [0, 5]: {val}', intent=extraction.intent)
                parsed_operand = val
            elif prop.constraint_type == 'year':
                num_match = re.search(r'\b(19\d\d|20\d\d)\b', prop.exact_source_substring)
                if not num_match:
                    return NormalizationResult(is_valid=False, rejection_reason='Invalid publication year', intent=extraction.intent)
                parsed_operand = int(num_match.group(0))
            else:
                parsed_operand = prop.exact_source_substring

        resolved.append(ResolvedConstraint(
            constraint_type=prop.constraint_type,
            source_span=span,
            source_text=query[span[0]:span[1]],
            modality=prop.modality,
            state=prop.state,
            resolved_operand=parsed_operand
        ))

    return NormalizationResult(
        is_valid=True,
        intent=extraction.intent,
        resolved_constraints=resolved
    )

def build_lmformatenforcer_parser():
    """Build a JsonSchemaParser using lmformatenforcer for constrained decoding."""
    try:
        from lmformatenforcer import JsonSchemaParser
        schema = CompactExtraction.model_json_schema()
        return JsonSchemaParser(schema)
    except Exception as e:
        return None
