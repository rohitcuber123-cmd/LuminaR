"""Source-first v2 review packet and fail-closed review decision checks."""
from __future__ import annotations

import csv
from datetime import date
import hashlib
import json
from pathlib import Path

from rag_domain_common import TRAINING
from rag_domain_qa_v2 import EntailmentResult, RuleEntailmentJudge, validate

CHECKS = ("premise_correct", "question_clear", "answer_correct", "evidence_supports_answer",
          "self_contained", "category_correct", "no_outside_context")
FIELDS = ("candidate_id", "decision", "reviewer", "review_date", *CHECKS,
          "edited_question", "edited_answer", "edited_category", "edited_evidence",
          "edited_proposition_json", "edited_asked_slot", "review_notes")
CSV = TRAINING / "reports" / "rag_domain_qa_review_v2.csv"
PACKET = TRAINING / "reports" / "rag_domain_qa_review_v2.md"


def render(candidates):
    current = {}
    if CSV.exists():
        with CSV.open(newline="", encoding="utf-8-sig") as f:
            current = {r["candidate_id"]: r for r in csv.DictReader(f)}
    ids = {c["candidate_id"] for c in candidates}
    if set(current) - ids:
        raise RuntimeError("Existing v2 review CSV refers to absent candidates")
    CSV.parent.mkdir(parents=True, exist_ok=True)
    with CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for c in candidates:
            writer.writerow(current.get(c["candidate_id"], {"candidate_id": c["candidate_id"]}))
    lines = ["# LuminaR proposition-first domain QA pilot review", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             "These are AUTO_VALIDATED candidates only. They are not REVIEWED training examples. "
             "Check the exact source passage and proposition roles before marking APPROVE or EDIT. "
             "The CSV preserves decisions on rerender. Retriever ranks and hard negatives are absent.", ""]
    for c in candidates:
        p = c["proposition"]
        val = c.get("auto_validation") or {}
        lines += [f"## {c['candidate_id']} — {c['book_title']}", "",
                  f"- Chapter: {c['chapter']}; split: {c['split']}; category: {c['category']}; difficulty: {c['difficulty']}",
                  f"- Question: {c['question']}", f"- Short answer: {c['short_answer']}",
                  f"- Asked slot: `{c['asked_slot']}`; answer type: `{c['answer_type']}`",
                  f"- Proposition: `{json.dumps({k: p.get(k) for k in ('subject','predicate','object','cause','effect','location','time','relation_type','location_direction','temporal_relation','relation_direction') if p.get(k)}, ensure_ascii=False)}`",
                  f"- Evidence: {p['evidence_quote']}",
                  f"- Source offsets: passage {c['source_start']}–{c['source_end']}; evidence {p['evidence_start']}–{p['evidence_end']}",
                  f"- Automatic checks: {val.get('rejection_reasons', [])}; entailment: {(val.get('entailment') or {}).get('label', 'UNCERTAIN')}",
                  "- Warning: automatic semantic judgment may miss role or premise errors; verify against the source.",
                  "", "```text", c["positive_passage"], "```", ""]
    PACKET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"candidates": len(candidates), "packet": str(PACKET), "review_csv": str(CSV)}


class CachedJudge:
    def judge(self, candidate):
        e = (candidate.get("auto_validation") or {}).get("entailment") or {}
        return EntailmentResult(e.get("label", "UNCERTAIN"), e.get("reason", ""), e.get("supporting_text", ""))


def review_decision(candidate, decision, source, *, eval_queries=(), test_works=(), semantic_judge=None):
    """Return (REVIEWED candidate or None, machine-readable rejection codes)."""
    action = (decision.get("decision") or "").strip().upper()
    if action == "REJECT": return None, ["HUMAN_REJECTED"]
    if action not in {"APPROVE", "EDIT"}: return None, ["MISSING_DECISION"]
    if not (decision.get("reviewer") or "").strip(): return None, ["REVIEWER_REQUIRED"]
    try:
        date.fromisoformat((decision.get("review_date") or "").strip())
    except ValueError:
        return None, ["REVIEW_DATE_REQUIRED"]
    if any((decision.get(k) or "").strip().upper() != "YES" for k in CHECKS):
        return None, ["CHECKLIST_INCOMPLETE"]
    c = json.loads(json.dumps(candidate))
    if action == "APPROVE" and any((decision.get(k) or "").strip() for k in
                                   ("edited_question", "edited_answer", "edited_category",
                                    "edited_evidence", "edited_proposition_json", "edited_asked_slot")):
        return None, ["APPROVE_WITH_EDIT_FIELDS"]
    if action == "EDIT":
        c["question"] = (decision.get("edited_question") or "").strip() or c["question"]
        c["short_answer"] = (decision.get("edited_answer") or "").strip() or c["short_answer"]
        c["category"] = (decision.get("edited_category") or "").strip() or c["category"]
        c["asked_slot"] = (decision.get("edited_asked_slot") or "").strip() or c["asked_slot"]
        new_evidence = (decision.get("edited_evidence") or "").strip()
        if new_evidence:
            raw_prop = (decision.get("edited_proposition_json") or "").strip()
            if not raw_prop: return None, ["EDITED_EVIDENCE_REQUIRES_PROPOSITION"]
            try: p = json.loads(raw_prop)
            except json.JSONDecodeError: return None, ["INVALID_EDITED_PROPOSITION"]
            if not isinstance(p, dict): return None, ["INVALID_EDITED_PROPOSITION"]
            passage = c["positive_passage"]
            if passage.count(new_evidence) != 1: return None, ["EVIDENCE_NOT_EXACT"]
            offset = passage.index(new_evidence)
            p.update({"evidence_quote": new_evidence, "source_sentence": new_evidence,
                      "evidence_start": c["source_start"] + offset,
                      "evidence_end": c["source_start"] + offset + len(new_evidence)})
            c["proposition"] = p
        elif (decision.get("edited_proposition_json") or "").strip():
            return None, ["PROPOSITION_EDIT_REQUIRES_EXPLICIT_EVIDENCE"]
        if not any((decision.get(k) or "").strip() for k in
                   ("edited_question", "edited_answer", "edited_category", "edited_evidence", "edited_asked_slot")):
            return None, ["EMPTY_EDIT"]
    if action == "EDIT" and semantic_judge is None:
        return None, ["EDIT_REQUIRES_FRESH_SEMANTIC_JUDGE"]
    checked = validate(c, source, eval_queries=eval_queries, test_works=test_works,
                       judge=semantic_judge if action == "EDIT" else CachedJudge())
    if checked["review_status"] != "AUTO_VALIDATED":
        return None, checked["auto_validation"]["rejection_reasons"] or ["SEMANTIC_ENTAILMENT_UNCERTAIN"]
    checked.update({"review_status": "REVIEWED", "reviewer": decision["reviewer"].strip(),
                    "reviewed_at": decision["review_date"].strip(), "review_action": action,
                    "review_notes": (decision.get("review_notes") or "").strip()})
    return checked, []
