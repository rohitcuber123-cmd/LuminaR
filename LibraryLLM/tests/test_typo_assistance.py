from search.typo_assistance import best_bounded_match, normalize_structured


def test_unicode_and_whitespace_normalization():
    assert normalize_structured("  I,  Robot ") == "i, robot"
    assert normalize_structured("C++") == "c++"


def test_obvious_bounded_title_typo():
    result = best_bounded_match("frankenstien", ["Frankenstein", "Dracula"])
    assert result and result["value"] == "Frankenstein"


def test_short_ambiguous_query_is_not_corrected():
    assert best_bounded_match("AI", ["AI", "A.I."]) is None


def test_close_candidates_are_rejected():
    assert best_bounded_match("programing", ["programming", "programing"], margin=0.2) is None


def test_no_match():
    assert best_bounded_match("frankenstien", ["astronomy", "programming"]) is None
