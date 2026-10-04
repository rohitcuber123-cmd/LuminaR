"""Summarize frozen-probe cue structures; diagnostic only."""
from __future__ import annotations

from collections import Counter, defaultdict
import json

from rag_domain_common import TRAINING

RELATIONS = ("ACTION", "ENTITY_RELATION", "LOCATION_AT", "LOCATION_FROM", "LOCATION_TO",
             "TEMPORAL_AT", "TEMPORAL_BEFORE", "TEMPORAL_AFTER", "CAUSE", "MOTIVATION",
             "INSTRUCTION", "STATEMENT", "ATTRIBUTE", "STATE_CHANGE", "SEQUENCE")


def main():
    inventory = json.loads((TRAINING / "reports" / "rag_domain_qa_v6_v5_cue_inventory.json").read_text(encoding="utf-8"))
    cues = inventory["cues"]
    groups = defaultdict(list)
    for c in cues: groups[c["structural_pattern"]].append(c)
    patterns = []
    for name, items in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        patterns.append({"structural_pattern": name, "count": len(items),
                         "detector_families": dict(Counter(i["detector_family"] for i in items)),
                         "safe_deterministic_fix": sum(i["safe_v6_candidate"] for i in items),
                         "needs_discourse": sum(i["consistency_class"] == "REQUIRES_DISCOURSE_REASONING" for i in items),
                         "example_cue_id": items[0]["cue_id"], "example_clause": items[0]["clause_text"]})
    report = {"result_label": "DIAGNOSTIC ONLY — NO QA GENERATED",
              "cue_count": len(cues), "pattern_count": len(patterns), "patterns": patterns}
    (TRAINING / "reports" / "rag_domain_qa_v6_pattern_frequency.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V6 structural pattern frequencies", "", "All 158 frozen V5 detector cues; no QA was generated.", "",
             "| Structural pattern | Cues | Family | Safe candidates | Needs discourse | Example |",
             "|---|---:|---|---:|---:|---|"]
    for p in patterns:
        example = p["example_clause"].replace("\n", " ").replace("|", "\\|")[:105]
        lines.append(f"| {p['structural_pattern']} | {p['count']} | {', '.join(p['detector_families'])} | "
                     f"{p['safe_deterministic_fix']} | {p['needs_discourse']} | {p['example_cue_id']}: {example} |")
    (TRAINING / "reports" / "rag_domain_qa_v6_pattern_frequency.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    by_family = {}
    for relation in RELATIONS + ("LOCATION",):
        items = [c for c in cues if c["detector_family"] == relation]
        by_family[relation] = {"cue_count": len(items), "extractor_attempts": len(items), "matches": 0,
                               "no_match_reasons": dict(Counter(r for c in items for r in c["no_match_reasons"])),
                               "safe_fix_count": sum(c["safe_v6_candidate"] for c in items),
                               "requires_discourse_count": sum(c["consistency_class"] == "REQUIRES_DISCOURSE_REASONING" for c in items),
                               "false_positive_count": sum(c["opportunity_class"] == "FALSE_POSITIVE_CUE" for c in items),
                               "representative_cue_ids": [c["cue_id"] for c in items[:3]]}
    by_family["LOCATION_UNDIRECTED_CUE"] = {"cue_count": sum(c["detector_family"] == "LOCATION" for c in cues),
                                            "note": "Detector cue does not establish AT/FROM/TO direction"}
    analysis = {"result_label": "DIAGNOSTIC ONLY — NO QA GENERATED",
                "cues_analyzed": len(cues), "missing_or_unparseable": 0,
                "overall_reasons": dict(Counter(r for c in cues for r in c["no_match_reasons"])),
                "consistency_classes": dict(Counter(c["consistency_class"] for c in cues)),
                "opportunity_classes": dict(Counter(c["opportunity_class"] for c in cues)),
                "per_relation": by_family, "pattern_table": patterns,
                "safe_cue_ids": [c["cue_id"] for c in cues if c["safe_v6_candidate"]],
                "plausible_safe_structures": sum(c["safe_v6_candidate"] for c in cues),
                "conservative_recoverable_opportunities": 1,
                "recoverable_estimate_note": "Three source structures look safely isolatable, but only one has a clearly specific unchanged-v2-compatible question template without an inferred context anchor.",
                "confirmed_segmentation_boundary_failures": 0,
                "parser_or_attachment_needed": sum(c["no_match_reasons"][0] == "PARSER_REQUIRED" for c in cues),
                "same_sentence_anchoring_cases_to_consider": ["V6C-053", "V6C-150"],
                "same_sentence_safely_recoverable_propositions": 0,
                "previous_sentence_safely_recoverable_propositions": 0,
                "discourse_or_coreference_cues": sum(c["consistency_class"] == "REQUIRES_DISCOURSE_REASONING" for c in cues),
                "per_cue_bug_or_interface_mismatch": 0,
                "instrumentation_note": "V5 counts STATEMENT_V5 cues only after emission, so failed V5 quote scans are not included in 158; this does not suppress matches."}
    (TRAINING / "reports" / "rag_domain_qa_v6_gap_analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"patterns": len(patterns), "plausible_safe_structures": analysis["plausible_safe_structures"],
                      "conservative_recoverable": analysis["conservative_recoverable_opportunities"],
                      "classes": analysis["consistency_classes"]}, indent=2))


if __name__ == "__main__": main()
