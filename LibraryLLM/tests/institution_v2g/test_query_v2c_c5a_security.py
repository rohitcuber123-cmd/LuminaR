"""Accepted B1/C1 assertions, unchanged functions, with a no-build C5A fixture.

The original query_library fixture builds isolated HNSW/KG. This version changes
only that fixture: identical authority/catalogue shape and actual NOT_BUILT
fallback; no production or fixture HNSW/KG rebuild is needed for state/security.
"""
import pytest
from test_intelligence import book
from test_query_v2c_b1 import (
    test_forgery_then_valid_preserves_full_mongo_state,
    test_downstream_status_does_not_invalidate,
    test_expiry_and_bad_operand_do_not_mutate_context,
    test_cross_clarification_and_newer_accepted_version,
    test_foreign_user_sid_scope_and_workspace_cannot_damage_either_context,
    test_interleaved_resolution_never_rolls_back_or_double_commits,
    test_failure_before_context_commit_releases_pending_without_consuming,
    test_error_after_commit_does_not_make_pending_reusable,
    test_forged_chip_addresses_cannot_inject_or_change_ownership,
    test_each_displayed_template_is_executable_and_enforced,
    test_late_expiry_before_first_context_insert_cannot_evict_another_context,
)
from test_query_v2c_c1 import (
    scopes,
    test_authorization_invalidation_matrix,
    test_denial_interleaving_never_erases_newer_authorized_state,
)
from test_query_v2c_b import (
    test_authorized_prefixes_and_forged_suggestion,
    test_private_denial_before_any_suggestions_cache,
    test_revocation_beats_cached_suggestions_and_choices,
    test_resolve_endpoint_single_use_and_no_plan_patch,
    test_removed_subject_rechecked_even_when_projection_warm,
    test_expired_jwt_and_legacy_sid_cannot_reach_suggestions,
    test_workspace_binding_survives_membership_role_change,
)

@pytest.fixture
def query_library(client,library,database):
    assert database.name.startswith('luminar_institution_v2g_test_')
    lid=library(private=True)
    response=client.post(f'/libraries/{lid}/join',headers={'x-test-user':'2'},json={'access_code':'Isolated fixture access code'})
    assert response.status_code==200,response.text
    row=book(client,lid,'Neural networks primer',linked=True)
    second=book(client,lid,'Deep learning handbook')
    for bid,subjects in [(row['library_book_id'],['Neural networks','Deep learning']),(second['library_book_id'],['Deep learning','Romance'])]:
        database.institution_library_books.update_one({'library_book_id':bid},{'$set':{'subjects':subjects}})
    database.books.update_one({'work_id':'OL1W'},{'$set':{'average_rating':4.5,'rating_count':2}})
    from search import personalization,query_suggestions
    personalization._cache.clear();query_suggestions._projections.clear();query_suggestions._issued.clear()
    return lid,row,second,None,None,None
