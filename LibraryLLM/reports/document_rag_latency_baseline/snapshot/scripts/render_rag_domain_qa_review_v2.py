"""Render v2 source-first packet for AUTO_VALIDATED candidates only."""
import json
from rag_domain_common import TRAINING, controls
from rag_domain_qa_v2_review import render


def main():
    controls()
    path = TRAINING / "luminar" / "domain_qa_auto_validated_v2.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    print(json.dumps(render(records), indent=2))


if __name__ == "__main__": main()
