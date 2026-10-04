"""Controlled V7R3 answer-first, question-second local Qwen pilot."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

from build_rag_domain_qa_candidates_v2 import LocalQwen
from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_assisted_v7 import decontamination_reasons
from rag_domain_qa_assisted_v7r3 import (parse_stage_a, parse_stage_b, parse_judge,
                                         question_reasons, validate_stage_a)
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units
from rag_domain_qa_word_units_v7r3 import build_word_units, tagged_units

STAGE_A_SYSTEM = ("Select at most TWO clear, independently useful facts from TARGET_PASSAGE. "
 "Output JSON only: {\"candidates\":[{\"evidence_unit_ids\":[\"S01\"],\"answer_unit_id\":\"S01\","
 "\"answer_start_word_id\":\"W004\",\"answer_end_word_id\":\"W004\",\"fact_type\":\"FACTUAL_DIRECT\","
 "\"fact_description\":\"Mr. Lloyd instructed Bessie.\",\"answer_type\":\"PERSON\"}]}. "
 "Zero candidates is valid. Select a contiguous meaningful answer span present in its answer unit; do not write "
 "the answer text or any question. Do not choose unresolved pronouns, partial names/times/quotes, auxiliaries, "
 "conjunctions, or dangling prepositions. Evidence is one unit or two adjacent units. "
 "fact_type must be FACTUAL_DIRECT, ENTITY_RELATION, EVENT, MOTIVATION, CAUSAL, LOCATION, TEMPORAL, "
 "SEMANTIC_PARAPHRASE, or QUOTE_OR_PHRASE. answer_type must be PERSON, PERSON_GROUP, LOCATION, TIME, "
 "CAUSE, EVENT, ACTION, RELATION, STATE, OBJECT, PHRASE, QUOTE, or OTHER_EXPLICIT. JSON only.")
STAGE_B_SYSTEM = ("Given a FIXED answer and FIXED evidence, write one self-contained, specific question whose exact "
 "answer is the fixed answer. Output JSON only: {\"question\":\"... ?\",\"difficulty\":\"EASY\"}. "
 "You may abstain with {\"question\":null,\"difficulty\":null,\"reason\":\"...\"}. "
 "Do not return answer, evidence, category, or explanations. Do not change the fact, introduce outside names or "
 "plot context, reveal the answer in the question, or use unresolved he/she/they/it/this/that. "
 "Use a question form appropriate to answer_type. Difficulty is EASY, MEDIUM, or HARD. JSON only.")
JUDGE_SYSTEM = ("Using ONLY the given authoritative evidence and passage, decide if the fixed answer correctly "
 "answers the question with the intended fact_type. Never use outside book knowledge or generator reasoning. "
 "Return JSON only, exactly: {\"label\":\"SUPPORTED\",\"outside_context\":false,"
 "\"wrong_role\":false,\"supporting_unit_ids\":[\"S01\"]}. "
 "label is SUPPORTED, UNSUPPORTED, or UNCERTAIN. Support unit IDs must be a nonempty subset of selected IDs "
 "when SUPPORTED. If unsure, UNCERTAIN. JSON only.")


def ask(local, system, payload, parser, *, tokens, retry=True):
    raw = local.ask(system, payload, max_tokens=tokens)
    parsed = parser(raw)
    if parsed is None and retry:
        raw = local.ask(system + " Return a single valid JSON object only; no Markdown.", payload, max_tokens=tokens)
        parsed = parser(raw)
    return raw, parsed


def jsonl(path, rows):
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-manifest", type=Path, required=True)
    ap.add_argument("--max-per-passage", type=int, default=2)
    ap.add_argument("--deterministic", action="store_true")
    args = ap.parse_args()
    expected = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    if args.source_manifest.resolve() != expected.resolve() or args.max_per_passage != 2 or not args.deterministic:
        raise ValueError("V7R3 requires the frozen original 50 manifest, max 2 and deterministic generation")
    old_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    word_path = TRAINING / "manifests" / "rag_domain_qa_v7r3_word_units.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    words = json.loads(word_path.read_text(encoding="utf-8"))
    manifest = json.loads(expected.read_text(encoding="utf-8"))["passages"]
    if not (len(old["passages"]) == len(words["passages"]) == len(manifest) == 50):
        raise RuntimeError("V7R3 source selection is not 50 passages")
    if old["source_manifest_sha256"] != hashlib.sha256(expected.read_bytes()).hexdigest() or words["source_units_manifest_sha256"] != hashlib.sha256(old_path.read_bytes()).hexdigest():
        raise RuntimeError("Frozen source manifest drift")
    out = TRAINING / "luminar"
    report_dir = TRAINING / "reports"
    paths = [out / f"domain_qa_assisted_v7r3_{x}.jsonl" for x in ("stage_a_raw", "stage_a_valid", "raw", "auto_checked", "rejected")]
    report_path = report_dir / "rag_domain_qa_assisted_v7r3_generation.json"
    if any(p.exists() for p in [*paths, report_path]):
        raise RuntimeError("V7R3 generation artifact already exists; refusing overwrite")
    saved, split, labels = controls()
    rows, quality = passage_pool(classifier=classify_passage_v2)
    lookup = {(r["work_id"], r["chunk_id"]): r for r in rows}
    selected = []
    for original, source_units, word_units in zip(manifest, old["passages"], words["passages"]):
        keys = ("work_id", "chunk_id", "source_start", "source_end", "source_hash")
        if any(original[k] != source_units[k] or original[k] != word_units[k] for k in keys):
            raise RuntimeError("Passage selection/order drift")
        row = lookup[(original["work_id"], original["chunk_id"])]
        if (row["split"], row["source_start_char"], row["source_end_char"], row["source_sha256"]) != (
            "TRAIN", original["source_start"], original["source_end"], original["source_hash"]):
            raise RuntimeError("Passage pool drift or TEST leakage")
        selected.append(row)
    if any(r["work_id"] in split["protected_test_work_ids"] for r in selected):
        raise RuntimeError("TEST leakage")
    eval_spans = {}
    for label in labels:
        eval_spans.setdefault(label["work_id"], []).extend(p for p in label["accepted_passages"] if p["relevance_grade"] == 2)
    for row in selected:
        if any(row["source_start_char"] < p["source_end"] and p["source_start"] < row["source_end_char"] for p in eval_spans.get(row["work_id"], [])):
            raise RuntimeError("Evaluation span leakage")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / source_map[wid]["source_file"]).read_text(encoding="utf-8") for wid in {r["work_id"] for r in selected}}
    for wid, source in sources.items():
        if hashlib.sha256(source.encode("utf-8")).hexdigest() != saved["source_hashes"][wid]:
            raise RuntimeError("Authoritative source hash drift")
    for row in selected:
        if sources[row["work_id"]][row["source_start_char"]:row["source_end_char"]] != row["text"]:
            raise RuntimeError("Authoritative passage offset drift")
    import psutil
    if psutil.virtual_memory().available < int(1.5 * 2**30):
        raise RuntimeError("Insufficient RAM")
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True)
    if int(gpu.stdout.strip().splitlines()[0]) < 6500:
        raise RuntimeError("Insufficient VRAM")
    local = LocalQwen()
    model_index = Path(local.model_id) / "model.safetensors.index.json"
    if hashlib.sha256(model_index.read_bytes()).hexdigest() != "bc8aaa0c87d4335177e01c765f1de0db81661c67c1a72fbfb0d521b09f5ddc56":
        raise RuntimeError("Frozen Qwen model snapshot changed")
    count = Counter()
    stage_a_raw, stage_a_valid, raw_rows, auto, rejected = [], [], [], [], []
    seen_questions, seen_facts, selected_spans = [], set(), set()
    eval_queries = [q["question"] for q in labels]
    for i, (row, source_units, word_entry) in enumerate(zip(selected, old["passages"], words["passages"]), 1):
        view = NormalizedSourceView.build(row["text"], row["source_start_char"], row["source_sha256"])
        units = build_source_units(view)
        word_units = build_word_units(view, units)
        if units != source_units["units"] or view.presentation_text != source_units["presentation_text"] or word_units != word_entry["word_units"]:
            raise RuntimeError("V7R2 source/word view drift")
        a_prompt = "<TARGET_PASSAGE>\n" + tagged_units(units, word_units) + "\n</TARGET_PASSAGE>\nSelect grounded fact spans by IDs."
        a_text, a_obj = ask(local, STAGE_A_SYSTEM, a_prompt, parse_stage_a, tokens=360)
        a_raw = {"passage_index": i, "work_id": row["work_id"], "chunk_id": row["chunk_id"],
                 "source_start": row["source_start_char"], "source_end": row["source_end_char"],
                 "source_hash": row["source_sha256"], "generator_raw": a_text, "candidate_ids": []}
        stage_a_raw.append(a_raw)
        if a_obj is None:
            count["invalid_stage_a_json"] += 1
            rejected.append({**a_raw, "rejection_reasons": ["INVALID_STAGE_A_JSON"]})
            continue
        if not a_obj["candidates"]: count["stage_a_zero_candidate_passages"] += 1
        for j, candidate in enumerate(a_obj["candidates"], 1):
            count["stage_a_raw_selections"] += 1
            cid = f"AQA7R3-{i:03d}-{j}"
            a_raw["candidate_ids"].append(cid)
            answer, evidence, reasons = validate_stage_a(candidate, view, units, word_units)
            if not reasons:
                span_key = (row["work_id"], row["source_start_char"], answer["answer_authoritative_start"], answer["answer_authoritative_end"])
                if span_key in selected_spans: reasons = ["DUPLICATE_SOURCE_SPAN"]
                else: selected_spans.add(span_key)
            if reasons:
                count.update("reason_" + r for r in reasons)
                rejected.append({"candidate_id": cid, "stage": "A", "work_id": row["work_id"], "chunk_id": row["chunk_id"],
                                 "rejection_reasons": reasons, "selection": candidate})
                continue
            count["stage_a_valid_facts"] += 1
            a_valid = {"candidate_id": cid, "work_id": row["work_id"], "chunk_id": row["chunk_id"],
                       "source_hash": row["source_sha256"], "selection": candidate, "answer": answer, "evidence": evidence}
            stage_a_valid.append(a_valid)
            selected_evidence = "\n".join(f"[{u['unit_id']}] {u['presentation_text']}" for u in units if u["unit_id"] in candidate["evidence_unit_ids"])
            b_payload = {"fixed_answer": answer["answer_presentation_text"], "evidence": selected_evidence,
                         "fact_type": candidate["fact_type"], "answer_type": candidate["answer_type"],
                         "selected_evidence_unit_ids": candidate["evidence_unit_ids"]}
            count["stage_b_calls"] += 1
            b_text, b_obj = ask(local, STAGE_B_SYSTEM, json.dumps(b_payload, ensure_ascii=False), parse_stage_b, tokens=120)
            raw_record = {"candidate_id": cid, "stage_a": candidate, "fixed_answer": answer,
                          "fixed_evidence": evidence, "stage_b_raw": b_text}
            raw_rows.append(raw_record)
            if b_obj is None:
                count["invalid_stage_b_json"] += 1
                rejected.append({**raw_record, "rejection_reasons": ["INVALID_STAGE_B_JSON"]})
                continue
            if b_obj["question"] is None:
                count["stage_b_abstentions"] += 1
                rejected.append({**raw_record, "rejection_reasons": ["STAGE_B_ABSTAINED"]})
                continue
            question = b_obj["question"].strip()
            reasons = []
            if b_obj["difficulty"] not in {"EASY", "MEDIUM", "HARD"}: reasons.append("INVALID_DIFFICULTY")
            reasons += question_reasons(question, answer["answer_authoritative_text"], candidate["answer_type"],
                                        candidate["fact_type"], evidence["evidence_quote_authoritative"], view.presentation_text)
            if reasons and set(reasons) <= {"QUESTION_UNRESOLVED_REFERENT", "QUESTION_LENGTH_OR_FORMAT"}:
                count["question_repairs_attempted"] += 1
                repair_payload = {**b_payload, "failed_question": question, "failures": reasons,
                                  "instruction": "Rewrite the question only. Keep fixed answer and evidence unchanged."}
                repair_text, repair_obj = ask(local, STAGE_B_SYSTEM, json.dumps(repair_payload, ensure_ascii=False), parse_stage_b, tokens=120, retry=False)
                raw_record["repair_raw"] = repair_text
                if repair_obj and repair_obj["question"] and repair_obj["difficulty"] in {"EASY", "MEDIUM", "HARD"}:
                    repaired = repair_obj["question"].strip()
                    repair_reasons = question_reasons(repaired, answer["answer_authoritative_text"], candidate["answer_type"],
                                                       candidate["fact_type"], evidence["evidence_quote_authoritative"], view.presentation_text)
                    if not repair_reasons:
                        question, b_obj, reasons = repaired, repair_obj, []
                        count["question_repairs_accepted"] += 1
            if reasons:
                count.update("reason_" + r for r in set(reasons))
                rejected.append({**raw_record, "rejection_reasons": sorted(set(reasons))})
                continue
            record = {"candidate_id": cid, "generation_version": "v7r3", "generation_method": "answer_first_question_second",
                      "generator_model": local.model_id, "work_id": row["work_id"], "book_title": row["title"],
                      "chapter": row["chapter"], "chunk_id": row["chunk_id"], "split": "TRAIN", "source_hash": row["source_sha256"],
                      "positive_source_start": row["source_start_char"], "positive_source_end": row["source_end_char"],
                      "positive_passage": row["text"], "presentation_passage": view.presentation_text,
                      "source_units": units, "question": question, "short_answer": answer["answer_authoritative_text"],
                      "evidence_quote": evidence["evidence_quote_authoritative"], "answer_unit_id": candidate["answer_unit_id"],
                      "answer_start_word_id": candidate["answer_start_word_id"], "answer_end_word_id": candidate["answer_end_word_id"],
                      "evidence_unit_ids": candidate["evidence_unit_ids"], "answer_type": candidate["answer_type"],
                      "category_proposed": candidate["fact_type"], "category_validated": candidate["fact_type"],
                      "difficulty_proposed": b_obj["difficulty"], "stage_a_fact_description_diagnostic": candidate["fact_description"],
                      "automatic_checks": {"passed": True, "rejection_reasons": []}, "semantic_audit": None,
                      "same_model_generator_judge": True, "review_status": "GENERATED", "reviewer": None, "review_date": None,
                      **answer, **evidence}
            d_reasons, fact = decontamination_reasons(record, eval_queries, seen_questions, seen_facts)
            if d_reasons:
                count.update("reason_" + r for r in d_reasons)
                rejected.append({**record, "review_status": "AUTO_REJECTED", "rejection_reasons": d_reasons})
                continue
            count["deterministic_passes"] += 1
            judge_payload = {"question": question, "authoritative_answer": record["short_answer"],
                             "authoritative_evidence": record["evidence_quote"], "positive_passage": row["text"],
                             "fact_type": candidate["fact_type"], "selected_evidence_unit_ids": candidate["evidence_unit_ids"]}
            judge_text = local.ask(JUDGE_SYSTEM, json.dumps(judge_payload, ensure_ascii=False), max_tokens=100)
            judgment = parse_judge(judge_text, candidate["evidence_unit_ids"])
            if judgment.get("failure_code") == "JUDGE_INVALID_JSON":
                judge_text = local.ask(JUDGE_SYSTEM + " JSON only. No commentary.", json.dumps(judge_payload, ensure_ascii=False), max_tokens=100)
                judgment = parse_judge(judge_text, candidate["evidence_unit_ids"])
            record["judge_raw"] = judge_text
            record["semantic_audit"] = judgment
            count["judge_" + judgment["label"]] += 1
            if judgment.get("failure_code"):
                count[judgment["failure_code"].lower()] += 1
            if judgment["label"] == "SUPPORTED":
                record["review_status"] = "AUTO_CHECKED"
                auto.append(record)
                seen_questions.append(question)
                seen_facts.add(fact)
                count["AUTO_CHECKED"] += 1
            else:
                record["review_status"] = "AUTO_REJECTED"
                rejected.append({**record, "rejection_reasons": [judgment.get("failure_code", "JUDGE_" + judgment["label"])]})
        print(f"{i}/50; Stage A valid {count['stage_a_valid_facts']}; deterministic {count['deterministic_passes']}; AUTO_CHECKED {count['AUTO_CHECKED']}", flush=True)
        if psutil.virtual_memory().available < int(.75 * 2**30):
            raise RuntimeError("Available RAM below 0.75 GiB")
    report = {"result_label": "EXPERIMENTAL ONLY — NOT HUMAN REVIEWED", "version": "v7r3", "passages": 50,
              "source_manifest_sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
              "source_units_manifest_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
              "word_units_manifest_sha256": hashlib.sha256(word_path.read_bytes()).hexdigest(),
              "generator_model": local.model_id, "generator_model_index_sha256": hashlib.sha256(model_index.read_bytes()).hexdigest(),
              "dtype": "float16", "device": "cuda", "do_sample": False, "max_new_tokens_stage_a": 360,
              "max_new_tokens_stage_b": 120, "max_new_tokens_judge": 100, "same_model_generator_judge": True,
              "summary": dict(count), "quality_filter_counts": quality, "test_leakage": 0,
              "evaluation_span_leakage": 0, "human_review_status": "NOT_REVIEWED"}
    for path, items in zip(paths, (stage_a_raw, stage_a_valid, raw_rows, auto, rejected)):
        jsonl(path, items)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passages": 50, "summary": dict(count)}, indent=2))


if __name__ == "__main__": main()
