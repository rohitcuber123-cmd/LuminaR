"""Build word IDs without changing the frozen V7R2 source presentation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING
from rag_domain_qa_source_units_v7r2 import NormalizedSourceView, build_source_units
from rag_domain_qa_word_units_v7r3 import WORD_VERSION, build_word_units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-manifest", type=Path, required=True)
    args = ap.parse_args()
    expected = TRAINING / "manifests" / "rag_domain_qa_v7r1_original_passages.json"
    if args.source_manifest.resolve() != expected.resolve():
        raise ValueError("Only the frozen original 50-passage manifest is allowed")
    old_path = TRAINING / "manifests" / "rag_domain_qa_v7r2_source_units.json"
    old = json.loads(old_path.read_text(encoding="utf-8"))
    if old["source_manifest_sha256"] != hashlib.sha256(expected.read_bytes()).hexdigest():
        raise RuntimeError("V7R2 source manifest hash drift")
    if len(old["passages"]) != 50:
        raise RuntimeError("Expected 50 passages")
    source_map = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / info["source_file"]).read_text(encoding="utf-8")
               for wid, info in source_map.items() if any(p["work_id"] == wid for p in old["passages"])}
    originals = json.loads(expected.read_text(encoding="utf-8"))["passages"]
    entries = []
    for saved in old["passages"]:
        original = originals[saved["passage_index"] - 1]
        if any(original[k] != saved[k] for k in ("work_id", "chunk_id", "source_start", "source_end", "source_hash")):
            raise RuntimeError("Original passage selection drift")
        text = sources[saved["work_id"]][saved["source_start"]:saved["source_end"]]
        view = NormalizedSourceView.build(text, saved["source_start"], saved["source_hash"])
        if view.presentation_text != saved["presentation_text"] or build_source_units(view) != saved["units"]:
            raise RuntimeError("Frozen source presentation changed")
        word_units = build_word_units(view, saved["units"])
        for unit, item in zip(saved["units"], word_units):
            for w in item["words"]:
                if (view.presentation_text[w["presentation_start"]:w["presentation_end"]] != w["presentation_surface"] or
                    text[w["authoritative_start"]:w["authoritative_end"]] != w["authoritative_surface"] or
                    not unit["presentation_start"] <= w["presentation_start"] < w["presentation_end"] <= unit["presentation_end"]):
                    raise RuntimeError("Word offset mapping failed")
        entries.append({k: saved[k] for k in ("passage_index", "work_id", "chunk_id", "source_start", "source_end", "source_hash")}
                       | {"word_units": word_units})
    out = TRAINING / "manifests" / "rag_domain_qa_v7r3_word_units.json"
    if out.exists():
        raise RuntimeError("V7R3 word manifest exists; refusing overwrite")
    payload = {"version": WORD_VERSION, "source_manifest_sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
               "source_units_manifest_sha256": hashlib.sha256(old_path.read_bytes()).hexdigest(),
               "passages": entries}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passages": len(entries), "source_units": sum(len(x["word_units"]) for x in entries),
                      "word_positions": sum(len(u["words"]) for x in entries for u in x["word_units"])}))


if __name__ == "__main__": main()
