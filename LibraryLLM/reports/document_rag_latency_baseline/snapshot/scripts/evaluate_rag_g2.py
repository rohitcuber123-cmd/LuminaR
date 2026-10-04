"""Compare frozen DEV raw dense retrieval: baseline A versus isolated G2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.evaluate_rag_chunk_variants import evaluate_variant
from rag.evaluation.metrics import overlaps

TRAIN = ROOT / "datasets" / "training"
CORPUS = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"
BASELINE = TRAIN / "reports" / "rag_g2_baseline_reproduction.json"
G2_INDEX = TRAIN / "evaluation_indexes" / "minilm_g2_nq_50k"
G2_MODEL = TRAIN / "models" / "minilm_g2_nq_50k_full"
OUT = TRAIN / "reports" / "rag_g2_nq_eval.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_control() -> list[dict]:
    from nq_g2_controls import verify
    verify()
    control = json.loads((TRAIN / "manifests" / "control_v1.json").read_text(encoding="utf-8"))
    if sha(CORPUS / "chunks.parquet") != control["chunks_parquet_sha256"] or sha(LABELS) != control["evaluation_labels_sha256"]:
        raise RuntimeError("Frozen corpus or labels changed")
    production = json.loads((ROOT / "datasets" / "rag_experiments" / "chunking_v1" /
                             "reports" / "production_before_sha256.json").read_text(encoding="utf-8"))
    if any(not (ROOT / p).exists() or sha(ROOT / p) != digest for p, digest in production.items()):
        raise RuntimeError("Production snapshot changed")
    questions = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]
    return [q for q in questions if q["split"] == "DEV"]


def baseline(questions: list[dict]) -> dict:
    old = json.loads((TRAIN / "reports" / "baseline_a_previous.json").read_text(encoding="utf-8"))
    if not BASELINE.exists():
        from train_nq_biencoder_g2 import local_base_model
        model = SentenceTransformer(str(local_base_model()),
                                    device="cuda" if torch.cuda.is_available() else "cpu",
                                    local_files_only=True)
        evaluate_variant("tokens_220", model, questions, output_file=BASELINE)
    result = json.loads(BASELINE.read_text(encoding="utf-8"))
    historic = {q["query_id"]: q for q in old["queries"] if q["split"] == "DEV"}
    if set(historic) != {q["query_id"] for q in result["queries"]}:
        raise RuntimeError("Historical baseline query set mismatch")
    mismatch = [q["query_id"] for q in result["queries"]
                if [c["chunk_id"] for c in q["top50"]]
                != [c["chunk_id"] for c in historic[q["query_id"]]["top50"]]]
    if mismatch:
        raise RuntimeError(f"Baseline Top50 mismatch: {mismatch}")
    print("Baseline A: exact Top50 ID reproduction; metrics:",
          result["summary"]["metrics"], flush=True)
    return result


def excerpt(row: dict | None, texts: dict[str, str]) -> dict | None:
    if row is None:
        return None
    return {"rank": row["rank"], "chunk_id": row["chunk_id"],
            "similarity": row["similarity"],
            "text_excerpt": texts.get(row["chunk_id"], "")[:450]}


def compare(a: dict, b: dict) -> dict:
    books = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))['books']
    prior = {q["query_id"]: q for q in a["queries"]}
    dev_labels = {q["query_id"]: q for q in json.loads(
        LABELS.read_text(encoding="utf-8"))["questions"] if q["split"] == "DEV"}
    texts = {r["chunk_id"]: r["text"] for r in pq.read_table(
        CORPUS / "chunks.parquet", columns=["chunk_id", "text"]).to_pylist()}
    changes = []
    for now in b["queries"]:
        old = prior[now["query_id"]]
        label = dev_labels[now["query_id"]]
        if old["metrics"] is None or now["metrics"] is None:
            continue
        before, after = old["metrics"]["first_rank"], now["metrics"]["first_rank"]
        status = ("IMPROVED" if (after or float("inf")) < (before or float("inf"))
                  else "REGRESSED" if (after or float("inf")) > (before or float("inf"))
                  else "UNCHANGED")
        movement = {
            "query_id": now["query_id"], "work_id": now["work_id"],
            "book": books[now['work_id']]['title'], "question": label['question'],
            "status": status, "a_first_gold_rank": before,
            "g2_first_gold_rank": after,
            "recovered_top50": before is None and after is not None,
            "lost_top50": before is not None and after is None,
        }
        spans = [p for p in label["accepted_passages"] if p["relevance_grade"] == 2]
        def span_ranks(candidates):
            return [next((c["rank"] for c in candidates
                          if overlaps({"start": c["source_start"], "end": c["source_end"]}, span)), None)
                    for span in spans]
        movement["a_gold_span_ranks"] = span_ranks(old["top50"])
        movement["g2_gold_span_ranks"] = span_ranks(now["top50"])
        if movement["recovered_top50"] or movement["lost_top50"]:
            movement["question"] = label["question"]
            movement["gold_span_excerpts"] = [p["text_excerpt"][:450] for p in spans]
            movement["a_first_accepted"] = excerpt(old["first_accepted"], texts)
            movement["g2_first_accepted"] = excerpt(now["first_accepted"], texts)
            movement["a_nearest"] = [excerpt(r, texts) for r in old["top50"][:3]]
            movement["g2_nearest"] = [excerpt(r, texts) for r in now["top50"][:3]]
        changes.append(movement)
    return {
        "result_label": "EXPERIMENTAL / DESCRIPTIVE — DRAFT DEV LABELS",
        "experiment": "G2_NATURAL_QUESTIONS", "split": "DEV", "test_evaluated": False,
        "comparison": "original query; dense only; per-book IndexFlatIP; no expansion/reranker/LLM/lexical/union",
        "a": a["summary"]["metrics"], "g2": b["summary"]["metrics"],
        "a_no_gold_top50": a["summary"]["no_gold_in_top50"],
        "g2_no_gold_top50": b["summary"]["no_gold_in_top50"],
        "counts": {key: sum(x["status"] == key for x in changes)
                   for key in ("IMPROVED", "REGRESSED", "UNCHANGED")},
        "recovered_top50": sum(x["recovered_top50"] for x in changes),
        "lost_top50": sum(x["lost_top50"] for x in changes),
        "per_query": changes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=["baseline", "g2"])
    parser.add_argument("--split", default="dev", choices=["dev"])
    parser.add_argument("--dense-only", action="store_true")
    parser.add_argument("--compare-baseline", action="store_true")
    args = parser.parse_args()
    if not args.dense_only:
        raise ValueError("G2 comparison must be dense only")
    questions = verify_control()
    a = baseline(questions)
    if args.model == "baseline":
        return
    if OUT.exists():
        raise FileExistsError("G2 evaluation exists; will not overwrite")
    manifest = json.loads((G2_INDEX / "manifest.json").read_text(encoding="utf-8"))
    index_manifest = json.loads((TRAIN / "manifests" / "minilm_g2_nq_50k_full.json").read_text(encoding="utf-8"))
    if sha(G2_INDEX / "faiss.index") != manifest["index_sha256"] or sha(G2_MODEL / "model.safetensors") != index_manifest["model_weights_sha256"]:
        raise RuntimeError("G2 index/model hash mismatch")
    model = SentenceTransformer(str(G2_MODEL), device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    dense_path = G2_INDEX / "dense_dev_evaluation.json"
    evaluate_variant("tokens_220", model, questions,
                     index_folder=G2_INDEX, output_file=dense_path)
    b = json.loads(dense_path.read_text(encoding="utf-8"))
    report = compare(a, b)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# G2 Natural Questions DEV dense retrieval", "",
             "Experimental/descriptive: DEV labels remain DRAFT. TEST was not evaluated.", "",
             "| Metric | Baseline A | G2 |", "|---|---:|---:|"]
    for name in ("mrr",):
        lines.append(f"| {name.upper()} | {report['a'][name]:.4f} | {report['g2'][name]:.4f} |")
    for key in ("1", "3", "5", "10", "20", "50"):
        lines.append(f"| Hit@{key} | {report['a']['hit'][key]:.4f} | {report['g2']['hit'][key]:.4f} |")
    for key in ("5", "10", "20", "50"):
        lines.append(f"| Recall@{key} | {report['a']['recall'][key]:.4f} | {report['g2']['recall'][key]:.4f} |")
    lines.append(f"| No gold in Top50 | {report['a_no_gold_top50']} | {report['g2_no_gold_top50']} |")
    lines.extend(["", f"Movement: {report['counts']}; recovered Top50: {report['recovered_top50']}; lost Top50: {report['lost_top50']}.", ""])
    for q in report["per_query"]:
        if q["recovered_top50"] or q["lost_top50"]:
            lines.extend([f"## {q['query_id']} ({q['work_id']})", "",
                          f"Question: {q['question']}", "",
                          f"A gold span ranks: {q['a_gold_span_ranks']}; G2 gold span ranks: {q['g2_gold_span_ranks']}.", "",
                          f"Accepted span: {q['gold_span_excerpts'][0].replace(chr(10), ' ') if q['gold_span_excerpts'] else 'N/A'}", ""])
            for side in ("a", "g2"):
                lines.append(f"{side.upper()} nearest:")
                lines.append("")
                for candidate in q[f"{side}_nearest"]:
                    lines.append(f"- #{candidate['rank']} `{candidate['chunk_id']}`: {candidate['text_excerpt'][:180].replace(chr(10), ' ')}")
                lines.append("")
    (TRAIN / "reports" / "rag_g2_nq_eval.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("a", "g2", "a_no_gold_top50",
                                                "g2_no_gold_top50", "counts",
                                                "recovered_top50", "lost_top50")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
