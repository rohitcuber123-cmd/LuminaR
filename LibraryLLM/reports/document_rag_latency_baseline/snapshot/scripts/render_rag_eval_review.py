"""Create a source-only review packet; never shows retriever ranks or scores."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
OUT = ROOT / 'reports' / 'rag_retrieval_v1_label_review.md'


def main():
    questions = json.loads(DATA.read_text(encoding='utf-8'))['questions']
    lines = [
        '# RAG retrieval v1 — independent source-label review', '',
        'Review the source excerpts without consulting any retriever output. For each',
        'question, verify the premise and answer, decide whether each span is directly',
        'answer-bearing, find omitted valid passages, and check boundary/neighbor notes.',
        'Record decisions in the versioned JSON; this packet itself does not mark labels',
        'reviewed. All current labels are assistant-authored DRAFTs.', '',
    ]
    for q in questions:
        lines += [f"## {q['query_id']} — {q['book_title']} ({q['split']})", '',
                  f"**Question:** {q['question']}", '',
                  f"**Category/difficulty/ambiguity:** {q['category']} / "
                  f"{q['difficulty']} / {q['ambiguity_type']}", '',
                  f"**Draft note:** {q['label_notes']}", '']
        if not q['accepted_passages']:
            lines += ['**No accepted passage; premise requires adjudication.**', '']
        for index, passage in enumerate(q['accepted_passages'], 1):
            lines += [f"**Passage {index}:** {passage['chapter']}, "
                      f"source [{passage['source_start']}, {passage['source_end']}), "
                      f"grade {passage['relevance_grade']}, "
                      f"neighbor allowance {passage['neighbor_allowance']}", '',
                      f"**Adjacent covering chunks:** {passage['adjacent_chunk_coverage']}", '',
                      '```text', passage['text_excerpt'], '```', '']
        lines += ['- [ ] Question premise and answer verified in the source',
                  '- [ ] All reasonable answer-bearing source spans added',
                  '- [ ] Span grade and boundaries verified',
                  '- [ ] Neighbor/overlap treatment verified',
                  '- Reviewer and date:', '', '---', '']
    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print(OUT)


if __name__ == '__main__':
    main()
