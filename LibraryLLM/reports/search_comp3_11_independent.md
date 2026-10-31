# Fresh independent qualification

One primary evaluation; fresh gold-blind capture after candidate/gold/masks/evaluator/structural audit/contract freeze. Author and reviewer are separate AI agents; human reviewers=0, actual model identity=NOT_EXPOSED. Reviewer saw only the query/context packet and normative contracts, not predictions, author labels or desired pass rates.

| Population | Typed | Execution | False execution | Missed valid |
|---|---:|---:|---:|---:|
| C5C644 (exposed) | 644/644 | 644/644 | 0/394 | 0/250 |
| c5e90 (exposed) | 90/90 | 90/90 | 0/60 | 0/30 |
| c5er150 (exposed) | 150/150 | 150/150 | 0/100 | 0/50 |
| smarteng150 (exposed) | 150/150 | 150/150 | 0/100 | 0/50 |
| Fresh independent | 92/150 | 107/150 | 25/100 | 18/50 |

Per-stratum results and all30 cells: [search_comp3_independent_metrics.json](D:/SDC/LibraryLLM/reports/search_comp3_independent_metrics.json); unchanged audit including sealed counts only: [search_comp3_final_structural_isolation.json](D:/SDC/LibraryLLM/reports/search_comp3_final_structural_isolation.json). Gates: [search_comp3_independent_gate_decision.json](D:/SDC/LibraryLLM/reports/search_comp3_independent_gate_decision.json). Candidate/gold were not changed after capture; no retry/rescore of revised code was presented as fresh. All errors and operand mismatches are retained. Finite150-context validation and AI review do not establish zero real-world risk.

**Fresh acceptance finding:** Primary result: typed92/150 (61.33%), execution107/150 (71.33%), false25/100, missed18/50, hard operand mismatch26/57 executed contexts. INCOMPLETE20/25, AMBIGUOUS15/25, NOTICE11/25, UNSUPPORTED10/25, CONTRADICTORY15/25. Strict fields51/150. All99 strict failure traces are retained in search_comp3_acceptance_error_analysis.json. No candidate or gold change followed this capture.
