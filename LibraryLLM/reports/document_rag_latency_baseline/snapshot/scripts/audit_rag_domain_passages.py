"""Report source-verified, non-TEST 220-token passage quality classes."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rag_domain_common import TRAINING, passage_pool


def main():
    rows, classes = passage_pool()
    for name in ("GOOD_FOR_QA", "WEAK_CONTEXT", "BOILERPLATE", "HEADER_ONLY",
                 "DIALOGUE_FRAGMENT_WITHOUT_CONTEXT", "TOO_SHORT", "TOO_AMBIGUOUS",
                 "MALFORMED", "EVALUATION_SPAN_OVERLAP", "PROTECTED_TEST"):
        classes.setdefault(name, 0)
    by_split = Counter(r["split"] for r in rows)
    by_book = Counter(r["work_id"] for r in rows)
    report = {"classification_counts": classes, "good_by_split": dict(by_split),
              "good_by_book": dict(sorted(by_book.items())),
              "quality_filter": "heuristic triage only; GOOD_FOR_QA does not imply a verified question",
              "example_chunk_ids": {split: [r["chunk_id"] for r in rows if r["split"] == split][:20]
                                    for split in ("TRAIN", "VALIDATION")}}
    out = TRAINING / "reports" / "rag_domain_passage_quality_v1.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("classification_counts", "good_by_split")}, indent=2))


if __name__ == "__main__":
    main()
