from scripts.mine_rag_domain_hard_negatives import safe_candidate


def qa():
    return {"work_id": "TRAIN", "chunk_id": "positive", "positive_passage": "Caroline plaited straw.",
            "evidence_start": 100, "evidence_end": 150, "short_answer": "plaited straw"}


def row(text="Another character worked in the garden.", *, start=500, work="TRAIN", chunk="negative"):
    return {"split": "TRAIN", "work_id": work, "chunk_id": chunk, "text": text,
            "source_start_char": start, "source_end_char": start + len(text)}


def test_negative_rejects_positive_overlap_answer_and_test_book():
    assert safe_candidate(qa(), row())[0]
    assert safe_candidate(qa(), row(work="TEST"))[1] == "WRONG_SPLIT_OR_BOOK"
    assert safe_candidate(qa(), row(chunk="positive"))[1] == "SAME_POSITIVE"
    assert safe_candidate(qa(), row(start=110))[1] == "EVIDENCE_OVERLAP"
    assert safe_candidate(qa(), row("She plaited straw for a living."))[1] == "ANSWER_TEXT_PRESENT"
