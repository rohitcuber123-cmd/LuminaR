import pytest
from scratch.search_proof_recovery_v8.parser import parse_query
from scratch.search_proof_recovery_v8.parser import executable
from scratch.search_v2c_c5er.candidate_search_v4.query_calibration import assess

FACETS=['Ecology','Astronomy','Fiction','Mystery']

def test_unknown_mandatory_content_is_not_discarded():
    p=parse_query('require gold-leaf engraving as a hard filter; include subject "Ecology"',FACETS)
    assert p.decision['decision_type']=='UNSUPPORTED' and not executable(p)

def test_known_mandatory_content_is_owned():
    p=parse_query('require books published from 2017 onward; include subject "Ecology"',FACETS)
    assert executable(p) and p.year_min==2017

def test_missing_broad_negative_operand():
    p=parse_query('exclude every record containing the text ...; by Alder Vale',FACETS)
    assert p.decision['decision_type']=='INCOMPLETE'

def test_grouping_ambiguity_survives_quote_ownership():
    p=parse_query('include subject "Ecology" or "Astronomy" and "Fiction"',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS'

def test_unique_scoped_subject_repair_is_advisory():
    p=parse_query('include subject "Ecolgoy"; by Alder Vale',FACETS)
    assert p.subjects==['Ecology'] and p.decision['decision_type']=='EXECUTABLE_WITH_NOTICE'
    assert assess(p)['policy']=='EXECUTE_WITH_NOTICE'

def test_unresolved_title_selection():
    p=parse_query('my title note lists two options; I do not know which title is intended; rated at least 3 stars',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS'

def test_nonmandatory_unavailable_metadata_remains_a_topic():
    assert executable(parse_query('books about gold-leaf engraving',FACETS))
