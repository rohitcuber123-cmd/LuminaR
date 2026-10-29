"""Test suite for compact proposal interface and deterministic normalization adapter."""
import pytest
from scratch.search_architecture_v10.extraction_compact import (
    CompactExtraction,
    CompactConstraintProposal,
    normalize_compact_proposal,
    resolve_unique_substring,
    build_lmformatenforcer_parser
)

def test_valid_compact_proposal_resolution():
    query = "Find books by Elena Marquez, rated at least 4.2, published after 2011"
    extraction = CompactExtraction(
        intent='SEARCH',
        proposals=[
            CompactConstraintProposal(constraint_type='author', exact_source_substring='Elena Marquez', modality='MANDATORY'),
            CompactConstraintProposal(constraint_type='rating', exact_source_substring='rated at least 4.2', modality='MANDATORY'),
            CompactConstraintProposal(constraint_type='year', exact_source_substring='published after 2011', modality='MANDATORY')
        ]
    )
    res = normalize_compact_proposal(query, extraction)
    assert res.is_valid
    assert len(res.resolved_constraints) == 3
    # Check author resolution
    auth = res.resolved_constraints[0]
    assert auth.constraint_type == 'author'
    assert auth.source_span == (14, 27)
    assert auth.source_text == 'Elena Marquez'
    # Check rating resolution
    rat = res.resolved_constraints[1]
    assert rat.constraint_type == 'rating'
    assert rat.resolved_operand == 4.2
    # Check year resolution
    yr = res.resolved_constraints[2]
    assert yr.constraint_type == 'year'
    assert yr.resolved_operand == 2011

def test_fabricated_substring_is_rejected():
    query = "Science fiction books about space exploration"
    extraction = CompactExtraction(
        intent='SEARCH',
        proposals=[
            CompactConstraintProposal(constraint_type='author', exact_source_substring='Isaac Asimov', modality='MANDATORY')
        ]
    )
    res = normalize_compact_proposal(query, extraction)
    assert not res.is_valid
    assert 'Fabricated substring not in query' in res.rejection_reason

def test_ambiguous_repeated_substring_is_rejected():
    query = "books by Arthur with books about history"
    extraction = CompactExtraction(
        intent='SEARCH',
        proposals=[
            CompactConstraintProposal(constraint_type='topic', exact_source_substring='books', modality='MANDATORY')
        ]
    )
    res = normalize_compact_proposal(query, extraction)
    assert not res.is_valid
    assert 'Ambiguous repeated substring in query' in res.rejection_reason

def test_out_of_bounds_rating_is_rejected():
    query = "books rated above 6.5"
    extraction = CompactExtraction(
        intent='SEARCH',
        proposals=[
            CompactConstraintProposal(constraint_type='rating', exact_source_substring='rated above 6.5', modality='MANDATORY')
        ]
    )
    res = normalize_compact_proposal(query, extraction)
    assert not res.is_valid
    assert 'Rating out of bounds' in res.rejection_reason

def test_lmformatenforcer_parser_initialization():
    parser = build_lmformatenforcer_parser()
    assert parser is not None
