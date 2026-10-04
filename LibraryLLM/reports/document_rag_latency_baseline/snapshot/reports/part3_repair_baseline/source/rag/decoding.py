"""Allow copying source phrases while still suppressing repetitive answers."""
from transformers.generation.logits_process import (
    LogitsProcessor, NoRepeatNGramLogitsProcessor, RepetitionPenaltyLogitsProcessor,
)


class AnswerRepetitionControl(LogitsProcessor):
    def __init__(self, prompt_length, penalty=1.15, ngram_size=3):
        self.prompt_length = prompt_length
        self.penalty = RepetitionPenaltyLogitsProcessor(penalty)
        self.ngrams = NoRepeatNGramLogitsProcessor(ngram_size)

    def __call__(self, input_ids, scores):
        # Retain the original soft penalty. Removing source tokens from it made
        # measured answers longer and more speculative. Only the hard n-gram
        # ban must exclude evidence: source names must remain copyable.
        scores = self.penalty(input_ids, scores)
        answer_ids = input_ids[:, self.prompt_length:]
        if answer_ids.shape[1] == 0:
            return scores
        return self.ngrams(answer_ids, scores)
