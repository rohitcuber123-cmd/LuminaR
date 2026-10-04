"""Optional strict JSON Qwen judge; deterministic validation always runs first."""
from __future__ import annotations

import json

from rag_domain_qa_v2 import EntailmentResult

REQUIRED = ("question_is_answered", "answer_matches_question", "evidence_supports_answer",
            "relation_direction_correct")


class StrictJSONEntailmentJudge:
    """A supplied local generator may retry malformed output once, then fails closed."""
    def __init__(self, generate):
        self.generate = generate

    def judge(self, candidate):
        p = candidate["proposition"]
        payload = {"question": candidate["question"], "answer": candidate["short_answer"],
                   "evidence": p["evidence_quote"], "local_passage": candidate["positive_passage"],
                   "structured_proposition": {k: p.get(k) for k in
                       ("subject", "predicate", "object", "cause", "effect", "location", "time",
                        "relation_type", "v3_relation")}}
        instruction = (
            "Use only the supplied evidence. Return one JSON object, no markdown: "
            "{\"label\":\"ENTAILED|NOT_ENTAILED|UNCERTAIN\","
            "\"question_is_answered\":true|false,\"answer_matches_question\":true|false,"
            "\"evidence_supports_answer\":true|false,\"relation_direction_correct\":true|false,"
            "\"reason\":\"short reason\",\"supporting_quote\":\"exact evidence substring\"}. "
            "If a role, direction, time, or cause is ambiguous, answer UNCERTAIN."
        )
        prompt = instruction + "\n" + json.dumps(payload, ensure_ascii=False)
        for _ in range(2):  # first attempt plus at most one retry
            raw = self.generate(prompt)
            try: result = json.loads(raw)
            except (TypeError, json.JSONDecodeError): continue
            if not isinstance(result, dict) or result.get("label") not in {
                    "ENTAILED", "NOT_ENTAILED", "UNCERTAIN"}:
                continue
            if not all(type(result.get(k)) is bool for k in REQUIRED): continue
            quote = result.get("supporting_quote")
            if not isinstance(quote, str) or (quote and quote not in p["evidence_quote"]): continue
            label = result["label"]
            if label == "ENTAILED" and (not all(result[k] for k in REQUIRED) or not quote):
                label = "UNCERTAIN"
            return EntailmentResult(label, str(result.get("reason", ""))[:300], quote)
        return EntailmentResult("UNCERTAIN", "Invalid judge JSON after one retry", "")


def local_qwen_judge():
    """Load only the already cached model when explicitly requested."""
    from build_rag_domain_qa_candidates_v2 import LocalQwen
    local = LocalQwen()
    return StrictJSONEntailmentJudge(lambda prompt: local.ask(
        "You are a strict source entailment verifier. Output JSON only.", prompt, max_tokens=140))
