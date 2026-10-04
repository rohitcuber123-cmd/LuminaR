"""
V7 Phase 3: Validator Ablation Study

Compares four configurations on 25 adversarial cases:
    A. V6 Top-3 Combined LLM validator (baseline)
    B. Fast Filter only (no LLM)
    C. Fast Filter + LLM validator (cascade)
    D. LLM validator without fast filter

Saves: eval_results_v7_validator_ablation.json
"""
import json
import os
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ["LUMINAR_MOCK_LLM"] = "0"

from rag.llm import LuminaRLLM
from rag.fast_filter import run_fast_filter


# ============================================================
# 25 ADVERSARIAL CASES (same as V6 validator ablation)
# ============================================================

CASES = [
    # STRONG EVIDENCE (1-3)
    {"id": 1, "type": "Strong evidence (Motivation)", "question": "Why does Victor create the creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
     "chunk_text": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet. It was already one in the morning; the rain pattered dismally against the panes, and my candle was nearly burnt out, when, by the glimmer of the half-extinguished light, I saw the dull yellow eye of the creature open.",
     "distractors": ["The summer months passed while I was thus engaged, heart and soul, in one pursuit. It was a most beautiful season; never did the fields bestow a more plentiful harvest.",
                     "Winter, spring, and summer passed away during my labours; but I did not watch the blossom or the expanding leaves."],
     "expected_verdict": "SUPPORTED"},

    {"id": 2, "type": "Strong evidence (Factual)", "question": "Where does Victor go to create the female creature?",
     "intent_data": {"intent": "FACTUAL", "actor": "Victor", "action": "create the female creature", "polarity": "positive"},
     "chunk_text": "I departed for Scotland, and pitched my tent upon the Orkney Islands, a desolate and appalling landscape, where I could complete my miserable work in solitude.",
     "distractors": ["I travelled through England and Scotland, and fixed upon a site in the northern highlands.",
                     "The scenery around was magnificent, but my mind was occupied with thoughts of gloom."],
     "expected_verdict": "SUPPORTED"},

    {"id": 3, "type": "Strong evidence (Consequence)", "question": "What happens after Jonathan Harker shaves in the mirror?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Jonathan Harker shaves in the mirror", "polarity": "positive"},
     "chunk_text": "As I was shaving, Dracula suddenly appeared behind me. Startled, I cut myself slightly. When I looked in the glass, there was no reflection of him at all!",
     "distractors": ["I put down the razor and turned around quickly, feeling a cold hand upon my shoulder.",
                     "The count looked closely at the trickle of blood upon my chin and his eyes blazed with a demoniac fury."],
     "expected_verdict": "SUPPORTED"},

    # WEAK EVIDENCE / UNSUPPORTED PREMISES (4-6)
    {"id": 4, "type": "Weak evidence (Unsupported)", "question": "Why does Dracula regret attacking his victims?",
     "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "attacking his victims", "polarity": "negative"},
     "chunk_text": "He lay like a filthy leech, exhausted with his repletion. I shuddered as I looked at him, and the thought of the evil he had done filled me with terror.",
     "distractors": ["The Count smiled a sinister smile and walked toward the window overlooking the precipice.",
                     "There was no sign of humanity or pity in his dark and sunken eyes."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 5, "type": "Unsupported question (Factual)", "question": "What happens after Victor creates the second female creature in Scotland?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the second female creature in Scotland", "polarity": "positive"},
     "chunk_text": "I thought of the promise I had made... I tore the female creature to pieces before she was ever brought to life. The monster, seeing his mate destroyed, howled in despair.",
     "distractors": ["The remains of the half-finished creature lay scattered across the stone floor of the hut.",
                     "I locked the door and vowed never again to resume this blasphemous undertaking."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 6, "type": "Unsupported (False Premise)", "question": "Why does Jonathan Harker kill Dracula when he finds him in the box?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "kill Dracula", "polarity": "positive"},
     "chunk_text": "I saw the Count lying in the earth box. I raised the shovel to strike him and sever his head, but as I looked at his eyes, a sudden paralysis overcame me, and the shovel slipped from my hands.",
     "distractors": ["The Count lay unmoving, his youthful face mockingly calm amid the ruined chapel.",
                     "I fled from the cellar in sheer panic, unable to strike the finishing blow."],
     "expected_verdict": "NOT_SUPPORTED"},

    # LEXICAL FALSE POSITIVES (7-9)
    {"id": 7, "type": "Lexical overlap (Relationship)", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "chunk_text": "Victor stood by the father of the bride, looking intensely sad.",
     "distractors": ["The wedding ceremony proceeded in solemn silence.",
                     "Elizabeth looked radiant though pale with anxiety."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 8, "type": "Lexical overlap (Motivation)", "question": "Why does the creature hate Victor?",
     "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive"},
     "chunk_text": "Victor felt a sudden hate for the creature that stood before him.",
     "distractors": ["The monster reached out his hand, seeking communion, but Victor shrank back in disgust.",
                     "A dreadful silence fell between creator and creation upon the frozen glacier."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 9, "type": "Lexical overlap (Dracula)", "question": "Why does Dracula travel to London?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "travel to London", "polarity": "positive"},
     "chunk_text": "Jonathan looked at the map of London, while Dracula sat silently in the castle library in Transylvania.",
     "distractors": ["The library was filled with English books, newspapers, and directories.",
                     "The Count questioned Harker closely on the manners and customs of English society."],
     "expected_verdict": "NOT_SUPPORTED"},

    # RELATIONSHIP REASONING (10-12)
    {"id": 10, "type": "Relationship false positive", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "chunk_text": "Alphonse Frankenstein was a respected magistrate in Geneva. Victor studied science at Ingolstadt.",
     "distractors": ["The magistrate was held in high esteem by his fellow citizens for his public integrity.",
                     "Victor had departed Geneva to pursue natural philosophy in Germany."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 11, "type": "Relationship true positive", "question": "Who is Victor's father?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
     "chunk_text": "My father, Alphonse Frankenstein, was respected by all who knew him, and watched over my childhood with immense tenderness.",
     "distractors": ["He filled several public situations with honour and reputation.",
                     "My mother was Caroline Beaufort, daughter of his dearest friend."],
     "expected_verdict": "SUPPORTED"},

    {"id": 12, "type": "Relationship false positive (Harker)", "question": "Who is Mina's husband?",
     "intent_data": {"intent": "RELATIONSHIP", "actor": "Mina", "target": "husband", "polarity": "positive"},
     "chunk_text": "Jonathan Harker admired Mina Murray's handwriting in her letters.",
     "distractors": ["She wrote with great precision and intelligence in her daily correspondence.",
                     "Harker kept every note in his locked travelling desk."],
     "expected_verdict": "NOT_SUPPORTED"},

    # POLARITY & NEGATION (13-16)
    {"id": 13, "type": "Negation mismatch (Action happened)", "question": "Why doesn't Victor create a companion for the monster?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a companion for the monster", "polarity": "negative"},
     "chunk_text": "I agreed to the monster's demand and immediately began gathering materials to build a second creature.",
     "distractors": ["The monster promised to depart forever to the wilds of South America.",
                     "I felt a heavy burden upon my soul as I acquiesced to his terrifying request."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 14, "type": "Negation mismatch (Action avoided)", "question": "Why does Victor create a female creature?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "positive"},
     "chunk_text": "I resolved never to complete the work, lest a race of devils be propagated upon the earth, and tore it to pieces.",
     "distractors": ["The howling fiend witnessed the destruction of his promised bride through the casement.",
                     "I trampled the half-finished remains beneath my feet."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 15, "type": "Negation correct match", "question": "Why doesn't Victor create a female creature?",
     "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "negative"},
     "chunk_text": "I shuddered to think that future generations might curse me as their pest, whose selfishness had not hesitated to buy its own peace at the price of the existence of the whole human race.",
     "distractors": ["They might even hate each other; the creature who already lived loathed his own deformity.",
                     "She might refuse to comply with a compact made before her creation."],
     "expected_verdict": "SUPPORTED"},

    {"id": 16, "type": "Negation mismatch (Harker)", "question": "Why does Jonathan Harker stay at Castle Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "stay at Castle Dracula", "polarity": "positive"},
     "chunk_text": "I realized with a sinking heart that the castle was a prison, and I was a prisoner! Every door was bolted and locked.",
     "distractors": ["I wandered through the dark corridors seeking any passage of escape.",
                     "The sheer drop from the castle window made descent impossible."],
     "expected_verdict": "NOT_SUPPORTED"},

    # TEMPORAL RELATION (17-19)
    {"id": 17, "type": "Temporal mismatch (Before/After)", "question": "What happens after Victor meets the monster on the glacier?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
     "chunk_text": "Before travelling to the glacier of Montanvert, Victor spent two weeks in Geneva mourning the death of William and Justine.",
     "distractors": ["His father urged him to take solace in the beauty of the surrounding valleys.",
                     "He wandered like an evil spirit through the familiar scenes of his youth."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 18, "type": "Temporal correct match", "question": "What happens after Victor meets the monster on the glacier?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
     "chunk_text": "After hearing the creature's long tale inside the hut on the Mer de Glace, Victor reluctantly agreed to make him a companion.",
     "distractors": ["They descended the mountain separately under the darkening twilight sky.",
                     "Victor returned to Geneva weighed down by the dreadful promise he had made."],
     "expected_verdict": "SUPPORTED"},

    {"id": 19, "type": "Temporal mismatch (Harker)", "question": "What does Harker do before entering Castle Dracula?",
     "intent_data": {"intent": "CONSEQUENCE", "action": "entering Castle Dracula", "temporal_relation": "BEFORE", "polarity": "positive"},
     "chunk_text": "After entering the castle courtyard, Harker was greeted by a tall old man with a long white moustache.",
     "distractors": ["The Count bowed courteously and welcomed him to his dwelling.",
                     "The heavy iron doors clanged shut behind the carriage."],
     "expected_verdict": "NOT_SUPPORTED"},

    # ACTOR / EVENT MISMATCH (20-22)
    {"id": 20, "type": "Actor mismatch (Dracula)", "question": "Why does Van Helsing want to destroy Dracula?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "destroy Dracula", "polarity": "positive"},
     "chunk_text": "Dracula wished to destroy the men who dared to meddle with his earth boxes.",
     "distractors": ["The Count swore vengeance upon the small band of companions.",
                     "He stalked the streets of London seeking Mina Harker."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 21, "type": "Event mismatch (Victor)", "question": "Why did Victor travel to England with Henry Clerval?",
     "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to England with Henry Clerval", "polarity": "positive"},
     "chunk_text": "Victor travelled to Ingolstadt alone to study chemistry and natural philosophy under Professor Waldman.",
     "distractors": ["His father had arranged his departure from Geneva two years earlier.",
                     "He found lodging near the university gates."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 22, "type": "Actor mismatch (Creature)", "question": "Who saves the drowning girl in the river?",
     "intent_data": {"intent": "FACTUAL", "actor": "Creature", "action": "saves the drowning girl", "polarity": "positive"},
     "chunk_text": "A rustic hunter rushed forward and dragged the drowning girl from the rapid river current.",
     "distractors": ["The girl's father embraced the hunter with tears of gratitude.",
                     "The monster watched from the thick foliage of the woods."],
     "expected_verdict": "NOT_SUPPORTED"},

    # INTENT / REMORSE BOUNDARIES (23-25)
    {"id": 23, "type": "Intent mismatch (Regret vs Motivation)", "question": "Why does Victor feel remorse for his creation?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
     "chunk_text": "I was seized with a fierce determination to hunt the creature down and slaughter him upon the frozen northern wastes.",
     "distractors": ["No obstacle of ice or storm would stay my relentless pursuit.",
                     "I vowed vengeance before the graves of my murdered family."],
     "expected_verdict": "NOT_SUPPORTED"},

    {"id": 24, "type": "Intent correct match (Regret)", "question": "Why does Victor feel remorse for his creation?",
     "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
     "chunk_text": "A terrible sense of guilt overwhelmed me; I felt as if I had unleashed an unquenchable curse upon the innocent, and wept bitter tears of remorse.",
     "distractors": ["The memory of William and Justine haunted my sleepless nights.",
                     "I looked upon myself as the true murderer of those I loved."],
     "expected_verdict": "SUPPORTED"},

    {"id": 25, "type": "Intent mismatch (Reaction vs Consequence)", "question": "How does Victor react when the creature awakens?",
     "intent_data": {"intent": "REACTION", "actor": "Victor", "action": "react when creature awakens", "polarity": "positive"},
     "chunk_text": "Three months later, Victor received a letter from his father informing him of William's tragic death.",
     "distractors": ["The letter arrived on a cold autumn morning in Ingolstadt.",
                     "Clerval observed the sudden pallor on his friend's face."],
     "expected_verdict": "NOT_SUPPORTED"},
]


def run_single_config(llm, cases, config_name, use_fast_filter, use_llm_validator):
    """Run one ablation configuration."""
    print(f"\n--- Running Config: {config_name} ---")
    records = []
    latencies = []
    fp_count = 0
    fn_count = 0
    correct_count = 0
    llm_calls = 0
    unsupported_total = sum(1 for c in cases if c["expected_verdict"] == "NOT_SUPPORTED")
    unsupported_detected = 0

    for c in cases:
        used_items = [{"text": c["chunk_text"]}] + [{"text": d} for d in c.get("distractors", [])]

        t0 = time.perf_counter()

        ff_decision = None
        ff_signals = {}
        llm_called = False
        pred_verdict = None

        # Step 1: Fast filter (if enabled)
        if use_fast_filter:
            ff_result = run_fast_filter(c["question"], c["intent_data"], used_items, mode="combined")
            ff_decision = ff_result["decision"]
            ff_signals = ff_result["signals"]

            if ff_decision == "FAST_REJECT":
                pred_verdict = "NOT_SUPPORTED"
            elif ff_decision == "FAST_ACCEPT":
                pred_verdict = "SUPPORTED"

        # Step 2: LLM validator (if needed)
        if pred_verdict is None and use_llm_validator:
            res = llm.validate_evidence(c["question"], c["intent_data"], used_items, mode="top-3-comb")
            pred_verdict = res.get("verdict", "NOT_SUPPORTED") if isinstance(res, dict) else res
            llm_called = True
            llm_calls += 1
        elif pred_verdict is None:
            # Fast filter only, no LLM, and no decision yet
            pred_verdict = "NOT_SUPPORTED"  # conservative default

        lat_ms = (time.perf_counter() - t0) * 1000
        latencies.append(lat_ms)

        exp_verdict = c["expected_verdict"]
        is_correct = (pred_verdict == exp_verdict)

        if is_correct:
            correct_count += 1
        else:
            if exp_verdict == "NOT_SUPPORTED" and pred_verdict == "SUPPORTED":
                fp_count += 1
            elif exp_verdict == "SUPPORTED" and pred_verdict == "NOT_SUPPORTED":
                fn_count += 1

        if exp_verdict == "NOT_SUPPORTED" and pred_verdict == "NOT_SUPPORTED":
            unsupported_detected += 1

        rec = {
            "id": c["id"],
            "type": c["type"],
            "question": c["question"],
            "expected_verdict": exp_verdict,
            "predicted_verdict": pred_verdict,
            "is_correct": is_correct,
            "fast_filter_decision": ff_decision,
            "fast_filter_signals": ff_signals,
            "llm_called": llm_called,
            "latency_ms": round(lat_ms, 2)
        }
        records.append(rec)

        status = "PASS" if is_correct else "FAIL"
        print(f"[{c['id']:02d}] {c['type'][:40]:<40} | Exp: {exp_verdict:<13} | Pred: {pred_verdict:<13} | FF: {str(ff_decision):<22} | LLM: {'Y' if llm_called else 'N'} | {status} ({lat_ms:.1f}ms)")

    accuracy = (correct_count / len(cases)) * 100
    unsupported_rate = (unsupported_detected / unsupported_total) * 100 if unsupported_total else 0.0

    result = {
        "config": config_name,
        "total_cases": len(cases),
        "correct_count": correct_count,
        "accuracy_percent": round(accuracy, 2),
        "false_positives": fp_count,
        "false_negatives": fn_count,
        "unsupported_premise_detection_percent": round(unsupported_rate, 2),
        "llm_calls": llm_calls,
        "llm_calls_avoided_percent": round((len(cases) - llm_calls) / len(cases) * 100, 2),
        "mean_latency_ms": round(float(np.mean(latencies)), 2),
        "median_latency_ms": round(float(np.median(latencies)), 2),
        "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
        "records": records
    }

    print(f"\n--> {config_name}: Accuracy={accuracy:.1f}% | FP={fp_count} | FN={fn_count} | "
          f"Unsupp={unsupported_rate:.1f}% | LLM Calls={llm_calls}/{len(cases)} | "
          f"Latency(mean)={np.mean(latencies):.2f}ms\n")

    return result


def main():
    print("=" * 80)
    print("V7 PHASE 3: VALIDATOR ABLATION STUDY (4 CONFIGURATIONS)")
    print("=" * 80)

    llm = LuminaRLLM()

    configs = [
        ("A_V6_LLM_Top3Comb",        False, True),   # V6 baseline: LLM only
        ("B_FastFilter_Only",          True,  False),  # Fast filter only
        ("C_FastFilter_Plus_LLM",      True,  True),   # Fast filter + LLM cascade
        ("D_LLM_NoFastFilter",         False, True),   # LLM without fast filter
    ]

    all_results = {}

    for config_name, use_ff, use_llm in configs:
        if config_name == "D_LLM_NoFastFilter" and "A_V6_LLM_Top3Comb" in all_results:
            import copy
            result = copy.deepcopy(all_results["A_V6_LLM_Top3Comb"])
            result["config"] = config_name
            all_results[config_name] = result
            print(f"\n--- Config {config_name}: Identical to A_V6_LLM_Top3Comb (reused) ---")
            continue
        result = run_single_config(llm, CASES, config_name, use_ff, use_llm)
        all_results[config_name] = result

    # Calculate comparison metrics
    baseline = all_results["A_V6_LLM_Top3Comb"]
    cascade = all_results["C_FastFilter_Plus_LLM"]

    comparison = {
        "llm_calls_avoided_percent": cascade["llm_calls_avoided_percent"],
        "validation_latency_saved_percent": round(
            (1 - cascade["mean_latency_ms"] / baseline["mean_latency_ms"]) * 100, 2
        ) if baseline["mean_latency_ms"] > 0 else 0.0,
        "accuracy_change_percent": round(
            cascade["accuracy_percent"] - baseline["accuracy_percent"], 2
        ),
        "fp_change": cascade["false_positives"] - baseline["false_positives"],
        "fn_change": cascade["false_negatives"] - baseline["false_negatives"],
    }

    output = {
        "configs": all_results,
        "comparison_cascade_vs_baseline": comparison
    }

    with open("eval_results_v7_validator_ablation.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 80)
    print("COMPARISON: CASCADE (C) vs BASELINE (A)")
    print("=" * 80)
    print(f"LLM Calls Avoided   : {comparison['llm_calls_avoided_percent']}%")
    print(f"Latency Saved        : {comparison['validation_latency_saved_percent']}%")
    print(f"Accuracy Change      : {comparison['accuracy_change_percent']:+.2f}%")
    print(f"FP Change            : {comparison['fp_change']:+d}")
    print(f"FN Change            : {comparison['fn_change']:+d}")
    print(f"\n[DONE] Saved to eval_results_v7_validator_ablation.json")


if __name__ == "__main__":
    main()
