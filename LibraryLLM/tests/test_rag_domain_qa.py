from scripts.rag_domain_common import controls, normalized_query, validate_candidate


def row():
    text = "Caroline Beaufort plaited straw to earn a pittance for her father."
    return {"text": text, "source_start_char": 100, "source_end_char": 100 + len(text),
            "source_sha256": "synthetic", "token_count": 25, "work_id": "synthetic",
            "title": "Synthetic", "chapter": "One", "chunk_id": "synthetic-1", "split": "TRAIN"}


def generated():
    return {"question": "What did Caroline Beaufort do to earn a pittance?",
            "short_answer": "plaited straw", "evidence_quote": row()["text"],
            "category": "FACTUAL_DIRECT", "difficulty": "EASY"}


def test_book_split_is_disjoint_and_derived_from_labels():
    _, split, labels = controls()
    test = {q["work_id"] for q in labels if q["split"] == "TEST"}
    assert test == set(split["protected_test_work_ids"])
    assert not test & set(split["train_work_ids"])
    assert not test & set(split["validation_work_ids"])


def test_exact_source_evidence_required():
    candidate, reasons = validate_candidate(row(), generated(), [])
    assert not reasons
    assert candidate["evidence_start"] == 100
    assert candidate["evidence_end"] == 100 + len(row()["text"])
    broken = generated()
    broken["evidence_quote"] = "Caroline earned money elsewhere."
    assert "EVIDENCE_NOT_UNIQUE_VERBATIM" in validate_candidate(row(), broken, [])[1]


def test_eval_query_near_duplicate_and_category_mismatch_rejected():
    question = generated()["question"]
    assert "EVALUATION_QUERY_DUPLICATE_OR_NEAR" in validate_candidate(row(), generated(), [question])[1]
    wrong = generated()
    wrong["category"] = "TEMPORAL"
    assert "CATEGORY_QUESTION_MISMATCH" in validate_candidate(row(), wrong, [])[1]
    assert normalized_query("What, did Caroline?") == "what did caroline"
