import torch
from rag.decoding import AnswerRepetitionControl


def test_source_ngrams_remain_copyable():
    processor = AnswerRepetitionControl(prompt_length=4)
    scores = torch.ones(1, 10)
    # The source already contains [1, 2, 3]; the answer must still be able to copy it.
    actual = processor(torch.tensor([[1, 2, 3, 4, 1, 2]]), scores)
    assert torch.isfinite(actual[0, 3])
    assert actual[0, 3] > 0


def test_answer_repetition_is_still_blocked():
    processor = AnswerRepetitionControl(prompt_length=4)
    actual = processor(torch.tensor([[7, 8, 9, 0, 1, 2, 3, 1, 2]]), torch.ones(1, 10))
    assert torch.isneginf(actual[0, 3])


def test_original_soft_repetition_penalty_is_preserved():
    scores = torch.ones(1, 10)
    actual = AnswerRepetitionControl(4)(torch.tensor([[1, 2, 3, 4]]), scores)
    assert 0 < actual[0, 1] < actual[0, 5]
