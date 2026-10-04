"""Controlled same-50 source-referenced assisted QA generation pilot."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess

from build_rag_domain_qa_candidates_v2 import LocalQwen
from build_rag_domain_qa_assisted_v7r1 import authoring_context
from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_assisted_v7 import decontamination_reasons
from rag_domain_qa_assisted_v7r2 import (candidate_record_v7r2, parse_judge_v7r2,
                                         strict_json_v7r2)
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units

SYSTEM = ("You create source-grounded literary retrieval QA by REFERENCE, not by copying evidence. "
          "Output ONLY JSON: {\"candidates\":[{\"question\":\"string\",\"answer_text\":\"string\","
          "\"answer_unit_id\":\"S01\",\"evidence_unit_ids\":[\"S01\"],\"category\":\"FACTUAL_DIRECT\","
          "\"difficulty\":\"EASY\",\"support_explanation\":\"string\"}]}. "
          "Return at most TWO candidates; {\"candidates\":[]} is valid and preferred when no clear "
          "self-contained pair is supported. Use ONLY unit IDs printed inside TARGET_PASSAGE. "
          "DO NOT COPY EVIDENCE TEXT into output. Choose one evidence unit or two adjacent units. "
          "answer_unit_id must be one of evidence_unit_ids. answer_text MUST be an exact contiguous "
          "substring copied from the DISPLAYED TEXT of answer_unit_id; do not paraphrase it. "
          "Allowed categories ONLY: FACTUAL_DIRECT, ENTITY_RELATION, EVENT, MOTIVATION, CAUSAL, "
          "LOCATION, TEMPORAL, SEMANTIC_PARAPHRASE, QUOTE_OR_PHRASE. "
          "Allowed difficulties ONLY: EASY, MEDIUM, HARD. Do not invent enum values. "
          "Question must stand alone and be answerable from TARGET_PASSAGE alone. Prefer names in "
          "TARGET_PASSAGE; do not invent names, use book knowledge, ask metadata questions, or rely "
          "on unexplained he/she/they/it/this/that/the man/the narrator. "
          "WHY requires explicit reason; WHEN complete explicit time; WHO explicit identity; WHERE "
          "explicit location. AUTHORING_CONTEXT may clarify identity but cannot supply answer evidence. "
          "support_explanation is diagnostic only.\n"
          "Synthetic example, not from evaluation data:\n"
          "<TARGET_PASSAGE>\n[S01] Mr. Lloyd instructed Bessie to keep Jane undisturbed during the night.\n"
          "[S02] Bessie agreed.\n</TARGET_PASSAGE>\n"
          "{\"candidates\":[{\"question\":\"Whom did Mr. Lloyd instruct to keep Jane undisturbed during the night?\","
          "\"answer_text\":\"Bessie\",\"answer_unit_id\":\"S01\",\"evidence_unit_ids\":[\"S01\"],"
          "\"category\":\"FACTUAL_DIRECT\",\"difficulty\":\"EASY\","
          "\"support_explanation\":\"S01 explicitly names the instructed person.\"}]}")
JUDGE_SYSTEM = ("Audit QA using only authoritative TARGET_PASSAGE and the selected evidence units. "
                "Never use external book knowledge or a generator explanation. Output ONLY strict JSON "
                "with exactly label (SUPPORTED|UNSUPPORTED|UNCERTAIN), question_answered_by_passage, "
                "answer_supported, question_self_contained, requires_outside_context, wrong_semantic_role "
                "(booleans), reason (string), supporting_unit_ids (array). supporting_unit_ids must be "
                "a nonempty subset of SELECTED_EVIDENCE_UNIT_IDS when SUPPORTED; never rescue using another unit. "
                "If unsure, UNCERTAIN.")


def generation_prompt(row, units, context_presentation):
    lines = "\n".join(f"[{u['unit_id']}] {u['presentation_text']}" for u in units)
    return (f"Book: {row['title']}\nChapter: {row['chapter']}\n"
            f"<TARGET_PASSAGE>\n{lines}\n</TARGET_PASSAGE>\n"
            f"<AUTHORING_CONTEXT>\n{context_presentation}\n</AUTHORING_CONTEXT>\n"
            "Reference unit IDs; never return evidence_quote. Copy answer_text exactly from its displayed unit.")


def ask_json(local, system, user, *, judge=False, max_tokens=480):
    raw = local.ask(system, user, max_tokens=max_tokens)
    parsed = strict_json_v7r2(raw, judge=judge)
    if parsed is None:
        raw = local.ask(system + " Return only valid JSON matching the schema. No Markdown or commentary.",
                        user, max_tokens=max_tokens)
        parsed = strict_json_v7r2(raw, judge=judge)
    return raw, parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-manifest", type=Path, required=True)
    ap.add_argument("--max-per-passage", type=int, default=2)
    ap.add_argument("--deterministic", action="store_true")
    args = ap.parse_args()
    expected = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    if args.source_manifest.resolve() != expected.resolve() or args.max_per_passage != 2 or not args.deterministic:
        raise ValueError("V7R2 requires the frozen original 50 manifest, max 2, and deterministic generation")
    outdir, report_dir = TRAINING / "luminar", TRAINING / "reports"
    outputs = [outdir / f"domain_qa_assisted_v7r2_{kind}.jsonl" for kind in ("raw", "auto_checked", "rejected")]
    outputs.append(report_dir / "rag_domain_qa_assisted_v7r2_generation.json")
    if any(p.exists() for p in outputs):
        raise RuntimeError("V7R2 artifacts already exist; refusing overwrite")
    _, split, labels = controls()
    manifest = json.loads(expected.read_text(encoding="utf-8"))["passages"]
    units_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    units_manifest = json.loads(units_path.read_text(encoding="utf-8"))
    if len(manifest) != len(units_manifest["passages"]) or len(manifest) != 50:
        raise RuntimeError("V7R2 source-unit manifest is not the same 50 passages")
    if units_manifest["source_manifest_sha256"] != hashlib.sha256(expected.read_bytes()).hexdigest():
        raise RuntimeError("Original source manifest changed after source-unit audit")
    rows, quality = passage_pool(classifier=classify_passage_v2)
    lookup = {(r["work_id"], r["chunk_id"]): r for r in rows}
    selected = []
    for old, saved in zip(manifest, units_manifest["passages"]):
        if (old["work_id"], old["chunk_id"], old["source_start"], old["source_end"], old["source_hash"]) != (
                saved["work_id"], saved["chunk_id"], saved["source_start"], saved["source_end"], saved["source_hash"]):
            raise RuntimeError("V7R2 source-unit selection drift")
        row = lookup[(old["work_id"], old["chunk_id"])]
        if (row["split"], row["source_start_char"], row["source_end_char"], row["source_sha256"]) != (
                "TRAIN", old["source_start"], old["source_end"], old["source_hash"]):
            raise RuntimeError("V7R2 source row drift")
        selected.append(row)
    if any(r["work_id"] in split["protected_test_work_ids"] for r in selected):
        raise RuntimeError("V7R2 TEST leakage")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {r["work_id"] for r in selected}}
    accepted = defaultdict(list)
    for q in labels:
        accepted[q["work_id"]].extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    import psutil
    if psutil.virtual_memory().available < int(1.5 * 2**30):
        raise RuntimeError("Insufficient available RAM to load local Qwen safely")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True)
    if int(gpu.stdout.strip().splitlines()[0]) < 6500:
        raise RuntimeError("Insufficient free VRAM for local Qwen FP16")
    local = LocalQwen()
    model_path = local.model_id
    model_index = Path(model_path) / "model.safetensors.index.json"
    eval_queries = [q["question"] for q in labels]
    seen_questions, seen_facts = [], set()
    raw_rows, auto_rows, rejected = [], [], []
    count = Counter()
    for i, (row, saved) in enumerate(zip(selected, units_manifest["passages"]), 1):
        source = sources[row["work_id"]]
        view = NormalizedSourceView.build(row["text"], row["source_start_char"], row["source_sha256"])
        units = build_source_units(view)
        if units != saved["units"] or view.presentation_text != saved["presentation_text"]:
            raise RuntimeError("V7R2 runtime source units drifted from audited manifest")
        context, context_start = authoring_context(row, source, accepted[row["work_id"]], local.tokenizer)
        context_view = NormalizedSourceView.build(context, context_start, row["source_sha256"])
        prompt = generation_prompt(row, units, context_view.presentation_text)
        generated_text, parsed = ask_json(local, SYSTEM, prompt, max_tokens=480)
        raw_record = {"passage_index": i, "work_id": row["work_id"], "chunk_id": row["chunk_id"],
                      "source_start": row["source_start_char"], "source_end": row["source_end_char"],
                      "source_hash": row["source_sha256"], "generator_raw": generated_text,
                      "candidate_ids": []}
        if parsed is None:
            count["invalid_json"] += 1
            raw_record["status"] = "FORMAT_FAILED"
            rejected.append({**raw_record, "rejection_reasons": ["INVALID_GENERATOR_JSON"]})
        else:
            if not parsed["candidates"]: count["zero_candidate_passages"] += 1
            for j, generated in enumerate(parsed["candidates"], 1):
                count["raw_proposals"] += 1
                cid = f"AQA7R2-{i:03d}-{j}"
                raw_record["candidate_ids"].append(cid)
                record, reasons = candidate_record_v7r2(row, generated, view=view, units=units,
                                                         context=context, context_start=context_start,
                                                         generator_model=model_path, source=source)
                if reasons:
                    for reason in reasons: count[f"reason_{reason}"] += 1
                    rejected.append({"candidate_id": cid, "work_id": row["work_id"],
                                     "chunk_id": row["chunk_id"], "review_status": "AUTO_REJECTED",
                                     "rejection_reasons": reasons, "generated": generated})
                    continue
                record["candidate_id"] = cid
                count["deterministic_passes"] += 1
                reasons, fact = decontamination_reasons(record, eval_queries, seen_questions, seen_facts)
                if reasons:
                    for reason in reasons: count[f"reason_{reason}"] += 1
                    record["review_status"] = "AUTO_REJECTED"
                    record["automatic_checks"] = {"passed": False, "rejection_reasons": reasons}
                    rejected.append(record)
                    continue
                judge_payload = {"question": record["question"], "answer_authoritative_text": record["short_answer"],
                                 "evidence_quote_authoritative": record["evidence_quote"],
                                 "positive_passage_authoritative": record["positive_passage"],
                                 "selected_evidence_unit_ids": record["evidence_unit_ids"]}
                judge_text, _ = ask_json(local, JUDGE_SYSTEM, json.dumps(judge_payload, ensure_ascii=False),
                                         judge=True, max_tokens=240)
                judgment = parse_judge_v7r2(judge_text, record["evidence_unit_ids"])
                record["semantic_audit"] = judgment
                count[f"semantic_{judgment['label']}"] += 1
                if judgment["label"] == "SUPPORTED":
                    record["review_status"] = "AUTO_CHECKED"
                    auto_rows.append(record)
                    count["AUTO_CHECKED"] += 1
                    seen_questions.append(record["question"])
                    seen_facts.add(fact)
                else:
                    record["review_status"] = "AUTO_REJECTED"
                    rejected.append(record)
        raw_rows.append(raw_record)
        if i % 5 == 0:
            print(f"{i}/50 passages; raw {count['raw_proposals']}; deterministic {count['deterministic_passes']}; AUTO_CHECKED {count['AUTO_CHECKED']}", flush=True)
        if psutil.virtual_memory().available < int(.75 * 2**30):
            raise RuntimeError("V7R2 stopped: available RAM fell below 0.75 GiB")
    report = {"result_label": "EXPERIMENTAL ONLY — NOT HUMAN REVIEWED", "version": "v7r2",
              "passages": 50, "max_candidates_per_passage": 2,
              "source_manifest_sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
              "source_units_manifest_sha256": hashlib.sha256(units_path.read_bytes()).hexdigest(),
              "generator_model": model_path, "generator_model_index_sha256": hashlib.sha256(model_index.read_bytes()).hexdigest(),
              "dtype": "float16", "device": "cuda", "do_sample": False,
              "max_new_tokens_generator": 480, "max_new_tokens_judge": 240,
              "same_model_generator_judge": True, "authoring_context_max_tokens": 600,
              "summary": dict(count), "quality_filter_counts": quality,
              "test_leakage": 0, "evaluation_span_leakage": 0,
              "human_review_status": "NOT_REVIEWED"}
    for path, items in zip(outputs[:3], (raw_rows, auto_rows, rejected)):
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
    outputs[3].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passages": 50, "summary": dict(count)}, indent=2))


if __name__ == "__main__": main()
