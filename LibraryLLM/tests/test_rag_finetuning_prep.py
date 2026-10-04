import re

from scripts.prepare_rag_finetuning_data import freeze_control, nq_pair, sentence_window, squad_pair


def tokenizer():
    class TestTokenizer:
        def encode(self, text, add_special_tokens=True):
            return re.findall(r"\w+|[^\w\s]", text) + (["<s>", "</s>"] if add_special_tokens else [])
    return TestTokenizer()


def test_frozen_corpus_integrity():
    control = freeze_control()
    assert control["chunk_count"] == 16895
    assert len(control["source_hashes"]) == 18


def test_squad_window_contains_annotated_answer_and_is_bounded():
    tok = tokenizer()
    context = "The ship sailed west. Captain Ahab hunted the white whale. The crew watched the sea."
    answer = "Captain Ahab"
    row = {"id": "test", "title": "test", "question": "Who hunted the white whale?",
           "context": context, "answers": {"text": [answer], "answer_start": [context.index(answer)]}}
    pair = squad_pair(row, tok)
    assert pair["answer"] in pair["positive"]
    assert pair["token_count"] <= 220
    row["answers"]["answer_start"] = [0]
    assert squad_pair(row, tok) is None


def test_nq_rejects_unanchored_answer_and_html():
    tok = tokenizer()
    words = ["Captain", "Ahab", "hunted", "the", "white", "whale", "."] * 5
    row = {"id": "test", "question": {"text": "Who hunted the white whale?"},
           "document": {"title": "Book", "tokens": {"token": words,
           "is_html": [False] * len(words)}},
           "annotations": {"short_answers": [{"start_token": [0], "end_token": [2],
                                            "text": ["Captain Ahab"]}],
                           "long_answer": [{"start_token": 0, "end_token": len(words)}]}}
    assert nq_pair(row, tok)["answer"] == "Captain Ahab"
    row["document"]["tokens"]["is_html"][0] = True
    assert nq_pair(row, tok) is None
