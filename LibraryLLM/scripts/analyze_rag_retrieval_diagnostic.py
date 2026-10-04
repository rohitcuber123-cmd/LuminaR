"""Summarize unlabeled RAG retrieval diagnostics without claiming relevance."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / 'reports' / 'rag_retrieval_diagnostic_20260925.json'
OUTPUT = ROOT / 'reports' / 'rag_retrieval_unlabeled_summary_20260925.json'


def shingles(text):
    words = re.findall(r'\w+', text.casefold())
    return set(zip(*(words[i:] for i in range(5))))


def duplicate_pairs(items):
    sets = [shingles(item['text']) for item in items]
    exact = near = 0
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            left, right = sets[i], sets[j]
            if left == right:
                exact += 1
                pairs.append((i + 1, j + 1, 1.0))
                continue
            union = len(left | right)
            similarity = len(left & right) / union if union else 0
            if similarity >= .8:
                near += 1
                pairs.append((i + 1, j + 1, round(similarity, 3)))
    return {'exact_pairs': exact, 'near_pairs_jaccard_0_8': near,
            'matching_pairs': pairs}


def main():
    rows = json.loads(DIAGNOSTIC.read_text(encoding='utf-8'))['records']
    summary = []
    for row in rows:
        ranked = row['reranked_all_candidates']
        summary.append({
            'id': row['id'],
            'dense_top1': row['dense_original_top50'][0]['chunk_id'],
            'reranked_top1': ranked[0]['chunk_id'],
            'original_dense_candidates': len(row['dense_original_top50']),
            'expanded_candidates': len(ranked),
            'top3_duplicate_pairs': duplicate_pairs(ranked[:3]),
            'top10_duplicate_pairs': duplicate_pairs(ranked[:10]),
        })
    result = {
        'note': 'No gold-passage labels: these are diversity/diagnostic counts, not accuracy.',
        'queries': len(rows), 'records': summary,
        'queries_with_exact_duplicate_top3': sum(
            bool(x['top3_duplicate_pairs']['exact_pairs']) for x in summary),
        'queries_with_near_duplicate_top3': sum(
            bool(x['top3_duplicate_pairs']['near_pairs_jaccard_0_8']) for x in summary),
        'queries_with_exact_duplicate_top10': sum(
            bool(x['top10_duplicate_pairs']['exact_pairs']) for x in summary),
        'queries_with_near_duplicate_top10': sum(
            bool(x['top10_duplicate_pairs']['near_pairs_jaccard_0_8']) for x in summary),
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'records'},
                     indent=2))


if __name__ == '__main__':
    main()
