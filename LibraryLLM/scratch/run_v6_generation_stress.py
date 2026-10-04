import json
import os
import sys
import time
import gc
import torch
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.qa import LuminaRAG

def main():
    print("=" * 80)
    print("V6 PHASE 7: GROUNDED GENERATION EVALUATION (32 QUERIES)")
    print("=" * 80)

    engine = LuminaRAG()

    # Pre-established test dataset with 32 comprehensive queries
    test_suite = [
        # 1. Factual (4)
        {
            "id": "gen_01",
            "category": "FACTUAL",
            "work_id": "OL45326637W",
            "query": "Where was Victor Frankenstein born?",
            "ground_truth_fact": "Geneva",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_02",
            "category": "FACTUAL",
            "work_id": "OL45326637W",
            "query": "What was the name of the professor at Ingolstadt who encouraged Victor's studies?",
            "ground_truth_fact": "M. Waldman (or M. Krempe)",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_03",
            "category": "FACTUAL",
            "work_id": "OL85892W",
            "query": "What is Count Dracula's castle location?",
            "ground_truth_fact": "Transylvania / Carpathians / Bistritz",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_04",
            "category": "FACTUAL",
            "work_id": "OL85892W",
            "query": "What ship transported Dracula to England?",
            "ground_truth_fact": "Demeter",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 2. Motivation (4)
        {
            "id": "gen_05",
            "category": "MOTIVATION",
            "work_id": "OL45326637W",
            "query": "Why does Victor want to create a living being from lifeless matter?",
            "ground_truth_fact": "To banish disease, bestow animation upon lifeless matter, and achieve scientific glory / gratitude of a new species.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_06",
            "category": "MOTIVATION",
            "work_id": "OL45326637W",
            "query": "Why does the creature demand a female companion from Victor?",
            "ground_truth_fact": "He is isolated, lonely, rejected by humanity, and promises to leave for South America if given a mate.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_07",
            "category": "MOTIVATION",
            "work_id": "OL85892W",
            "query": "Why does Count Dracula purchase property in London?",
            "ground_truth_fact": "To establish a lair in a populous city (Carfax estate) and prey upon its millions.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_08",
            "category": "MOTIVATION",
            "work_id": "OL85892W",
            "query": "Why does Dr. Seward keep a diary about Renfield?",
            "ground_truth_fact": "To study his zoophagous madness (consuming flies, spiders, birds) as a psychological case.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 3. Regret & Remorse (3)
        {
            "id": "gen_09",
            "category": "REGRET",
            "work_id": "OL45326637W",
            "query": "Why does Victor feel profound regret and guilt after Justine is executed?",
            "ground_truth_fact": "He knows his creation killed William and caused the innocent Justine's death, viewing himself as the true murderer.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_10",
            "category": "REGRET",
            "work_id": "OL45326637W",
            "query": "Why does the creature weep over Victor's corpse at the end of the novel?",
            "ground_truth_fact": "He regrets his violent revenge, feels self-loathing and remorse, and laments the death of his only creator.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_11",
            "category": "REGRET",
            "work_id": "OL85892W",
            "query": "Why does Dracula express sorrow and remorse for biting Lucy?",
            "ground_truth_fact": "False premise: Dracula shows zero remorse for preying on Lucy.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },

        # 4. Negated Motivation (4)
        {
            "id": "gen_12",
            "category": "NEGATED_MOTIVATION",
            "work_id": "OL45326637W",
            "query": "Why doesn't Victor finish creating the female creature in the Orkneys?",
            "ground_truth_fact": "He fears a race of devils propagating, that she might be more malignant or reject the monster's compact.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_13",
            "category": "NEGATED_MOTIVATION",
            "work_id": "OL45326637W",
            "query": "Why doesn't Victor tell the judges in Geneva that his monster murdered William?",
            "ground_truth_fact": "He fears being considered insane or having his story dismissed as ravings.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_14",
            "category": "NEGATED_MOTIVATION",
            "work_id": "OL85892W",
            "query": "Why doesn't Jonathan Harker escape from Castle Dracula through the main gates?",
            "ground_truth_fact": "All the doors and gates are locked and bolted; he is trapped as a prisoner.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_15",
            "category": "NEGATED_MOTIVATION",
            "work_id": "OL85892W",
            "query": "Why didn't Arthur Holmwood stake Lucy when she first fell ill?",
            "ground_truth_fact": "He did not know she had become an un-dead vampire until Van Helsing revealed the truth at her tomb.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 5. Relationship (4)
        {
            "id": "gen_16",
            "category": "RELATIONSHIP",
            "work_id": "OL45326637W",
            "query": "Who is Alphonse Frankenstein to Victor?",
            "ground_truth_fact": "Victor's father.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_17",
            "category": "RELATIONSHIP",
            "work_id": "OL45326637W",
            "query": "What is the relationship between Victor and Elizabeth Lavenza?",
            "ground_truth_fact": "Adopted sister/cousin and betrothed bride / wife.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_18",
            "category": "RELATIONSHIP",
            "work_id": "OL85892W",
            "query": "Who is Mina Murray's husband?",
            "ground_truth_fact": "Jonathan Harker.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_19",
            "category": "RELATIONSHIP",
            "work_id": "OL85892W",
            "query": "What is the relationship between Lucy Westenra and Mina Harker?",
            "ground_truth_fact": "Close, affectionate friends / confidantes.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 6. Temporal / Before-After (3)
        {
            "id": "gen_20",
            "category": "TEMPORAL",
            "work_id": "OL45326637W",
            "query": "What happens immediately after the creature's dull yellow eye opens?",
            "ground_truth_fact": "Victor is filled with horror and disgust, rushes out of the room, and cannot sleep.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_21",
            "category": "TEMPORAL",
            "work_id": "OL45326637W",
            "query": "What happens after Elizabeth is killed on their wedding night?",
            "ground_truth_fact": "Victor returns to Geneva, his father dies of grief, and Victor dedicates his remaining life to pursuing the monster.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_22",
            "category": "TEMPORAL",
            "work_id": "OL85892W",
            "query": "What does Jonathan Harker see before entering the castle courtyard in the carriage?",
            "ground_truth_fact": "Blue flames on the road, howling wolves, and the sinister driver with red eyes.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 7. Subject/Object Directionality Inversion (3)
        {
            "id": "gen_23",
            "category": "DIRECTIONALITY",
            "work_id": "OL45326637W",
            "query": "Why does Victor fear the monster?",
            "ground_truth_fact": "The monster is immensely strong, has murdered his family/friends, and threatened to be with him on his wedding night.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },
        {
            "id": "gen_24",
            "category": "DIRECTIONALITY",
            "work_id": "OL45326637W",
            "query": "Why does the monster fear Victor?",
            "ground_truth_fact": "False/Misaligned premise: The monster does not fear Victor; he dominates and torments him, though he desires his acknowledgment.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_25",
            "category": "DIRECTIONALITY",
            "work_id": "OL85892W",
            "query": "Why does Count Dracula fear Van Helsing and the holy wafer?",
            "ground_truth_fact": "Sacred objects (host/crucifix) burn/repel him and strip his demonic power.",
            "is_premise_valid": True,
            "expected_classification": "CORRECT"
        },

        # 8. Unsupported Premises & False Assumptions (4)
        {
            "id": "gen_26",
            "category": "UNSUPPORTED_PREMISE",
            "work_id": "OL45326637W",
            "query": "Why does Victor invite the creature to live with Elizabeth in Geneva?",
            "ground_truth_fact": "False premise: Victor never invited the creature to live with them; he loathed and fled from him.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_27",
            "category": "UNSUPPORTED_PREMISE",
            "work_id": "OL45326637W",
            "query": "What happens after the creature successfully integrates into the De Lacey family?",
            "ground_truth_fact": "False premise: The creature never integrated; Felix attacked him with a stick and the family fled.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_28",
            "category": "UNSUPPORTED_PREMISE",
            "work_id": "OL85892W",
            "query": "Why did Jonathan Harker poison Count Dracula at dinner in the castle?",
            "ground_truth_fact": "False premise: Harker never poisoned Dracula; Dracula never even ate dinner with him.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_29",
            "category": "UNSUPPORTED_PREMISE",
            "work_id": "OL85892W",
            "query": "Why did Lucy Westenra become a nun after recovering from her illness?",
            "ground_truth_fact": "False premise: Lucy never became a nun; she died and became an un-dead vampire.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },

        # 9. Lexical-Overlap Traps (3)
        {
            "id": "gen_30",
            "category": "LEXICAL_TRAP",
            "work_id": "OL45326637W",
            "query": "Why did Victor's father build the creature in Ingolstadt?",
            "ground_truth_fact": "False premise: Alphonse never built the creature; Victor built it alone.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_31",
            "category": "LEXICAL_TRAP",
            "work_id": "OL45326637W",
            "query": "Why does the monster kill Victor upon first meeting him in Chapter IV?",
            "ground_truth_fact": "False premise: The monster does not kill Victor in Chapter IV or anywhere in the book.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        },
        {
            "id": "gen_32",
            "category": "LEXICAL_TRAP",
            "work_id": "OL85892W",
            "query": "Why did Van Helsing buy Castle Dracula from Count Dracula?",
            "ground_truth_fact": "False premise: Van Helsing never bought Castle Dracula; Dracula bought Carfax in London through Harker.",
            "is_premise_valid": False,
            "expected_classification": "UNSUPPORTED"
        }
    ]

    results = []

    print(f"\nRunning {len(test_suite)} generation stress queries...\n")

    for idx, q in enumerate(test_suite, start=1):
        print(f"[{idx:02d}/{len(test_suite)}] [{q['category']}] {q['query']}")

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        t0 = time.perf_counter()
        try:
            res = engine.ask(question=q["query"], work_id=q["work_id"], depth="normal")
        except Exception as e:
            print(f"Error on {q['id']}: {e}")
            res = {"answer": f"Error: {e}", "verdict": "ERROR", "timing_ms": {}, "sources": []}

        wall_ms = (time.perf_counter() - t0) * 1000
        answer = res.get("answer", "")
        verdict = res.get("verdict", "NOT_SUPPORTED")

        # Groundedness Evaluation
        is_unsupported_detected = (
            "does not support the premise" in answer.lower()
            or "not establish" in answer.lower()
            or "never" in answer.lower()
            or "no evidence" in answer.lower()
            or "false" in answer.lower()
            or verdict == "NOT_SUPPORTED"
        )

        if not q["is_premise_valid"]:
            if is_unsupported_detected or "not" in answer.lower():
                classification = "UNSUPPORTED"
            else:
                classification = "HALLUCINATED"
        else:
            # Valid premise: check if answer is factually grounded or hallucinated
            low_ans = answer.lower()
            if verdict == "NOT_SUPPORTED":
                classification = "UNSUPPORTED"
            elif any(term.lower() in low_ans for term in q["ground_truth_fact"].split() if len(term) > 3):
                classification = "CORRECT"
            else:
                classification = "PARTIALLY_CORRECT"

        entry = {
            "id": q["id"],
            "category": q["category"],
            "query": q["query"],
            "work_id": q["work_id"],
            "ground_truth_fact": q["ground_truth_fact"],
            "is_premise_valid": q["is_premise_valid"],
            "expected_classification": q["expected_classification"],
            "actual_classification": classification,
            "verdict": verdict,
            "answer": answer,
            "top_source": res.get("sources", [{}])[0].get("chunk_id") if res.get("sources") else None,
            "timing_ms": res.get("timing_ms", {}),
            "wall_time_ms": round(wall_ms, 2)
        }

        results.append(entry)
        print(f"--> Verdict: {verdict} | Class: {classification} (Expected: {q['expected_classification']}) | Time: {wall_ms:.1f}ms\n")

        with open("eval_results_v6_generation.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    print("\n[DONE] Generation evaluation saved to eval_results_v6_generation.json")

if __name__ == "__main__":
    main()
