import json
import os
import sys
import time
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

def main():
    print("=" * 80)
    print("V6 PHASE 5: VALIDATOR ABLATION STUDY (TOP-1 vs TOP-3 IND vs TOP-3 COMB)")
    print("=" * 80)

    llm = LuminaRLLM()

    # Load 25 comprehensive benchmark cases
    cases = [
        # STRONG EVIDENCE (1-3)
        {
            "id": 1,
            "type": "Strong evidence (Motivation)",
            "question": "Why does Victor create the creature?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
            "chunk_text": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet. It was already one in the morning; the rain pattered dismally against the panes, and my candle was nearly burnt out, when, by the glimmer of the half-extinguished light, I saw the dull yellow eye of the creature open.",
            "distractors": [
                "The summer months passed while I was thus engaged, heart and soul, in one pursuit. It was a most beautiful season; never did the fields bestow a more plentiful harvest.",
                "Winter, spring, and summer passed away during my labours; but I did not watch the blossom or the expanding leaves."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 2,
            "type": "Strong evidence (Factual)",
            "question": "Where does Victor go to create the female creature?",
            "intent_data": {"intent": "FACTUAL", "actor": "Victor", "action": "create the female creature", "polarity": "positive"},
            "chunk_text": "I departed for Scotland, and pitched my tent upon the Orkney Islands, a desolate and appalling landscape, where I could complete my miserable work in solitude.",
            "distractors": [
                "I travelled through England and Scotland, and fixed upon a site in the northern highlands.",
                "The scenery around was magnificent, but my mind was occupied with thoughts of gloom."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 3,
            "type": "Strong evidence (Consequence)",
            "question": "What happens after Jonathan Harker shaves in the mirror?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Jonathan Harker shaves in the mirror", "polarity": "positive"},
            "chunk_text": "As I was shaving, Dracula suddenly appeared behind me. Startled, I cut myself slightly. When I looked in the glass, there was no reflection of him at all!",
            "distractors": [
                "I put down the razor and turned around quickly, feeling a cold hand upon my shoulder.",
                "The count looked closely at the trickle of blood upon my chin and his eyes blazed with a demoniac fury."
            ],
            "expected_verdict": "SUPPORTED"
        },
        
        # WEAK EVIDENCE / UNSUPPORTED PREMISES (4-6)
        {
            "id": 4,
            "type": "Weak evidence (Unsupported)",
            "question": "Why does Dracula regret attacking his victims?",
            "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "attacking his victims", "polarity": "negative"},
            "chunk_text": "He lay like a filthy leech, exhausted with his repletion. I shuddered as I looked at him, and the thought of the evil he had done filled me with terror.",
            "distractors": [
                "The Count smiled a sinister smile and walked toward the window overlooking the precipice.",
                "There was no sign of humanity or pity in his dark and sunken eyes."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 5,
            "type": "Unsupported question (Factual)",
            "question": "What happens after Victor creates the second female creature in Scotland?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the second female creature in Scotland", "polarity": "positive"},
            "chunk_text": "I thought of the promise I had made... I tore the female creature to pieces before she was ever brought to life. The monster, seeing his mate destroyed, howled in despair.",
            "distractors": [
                "The remains of the half-finished creature lay scattered across the stone floor of the hut.",
                "I locked the door and vowed never again to resume this blasphemous undertaking."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 6,
            "type": "Unsupported (False Premise)",
            "question": "Why does Jonathan Harker kill Dracula when he finds him in the box?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "kill Dracula", "polarity": "positive"},
            "chunk_text": "I saw the Count lying in the earth box. I raised the shovel to strike him and sever his head, but as I looked at his eyes, a sudden paralysis overcame me, and the shovel slipped from my hands.",
            "distractors": [
                "The Count lay unmoving, his youthful face mockingly calm amid the ruined chapel.",
                "I fled from the cellar in sheer panic, unable to strike the finishing blow."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # LEXICAL FALSE POSITIVES (7-9)
        {
            "id": 7,
            "type": "Lexical overlap (Relationship)",
            "question": "Who is Victor's father?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
            "chunk_text": "Victor stood by the father of the bride, looking intensely sad.",
            "distractors": [
                "The wedding ceremony proceeded in solemn silence.",
                "Elizabeth looked radiant though pale with anxiety."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 8,
            "type": "Lexical overlap (Motivation)",
            "question": "Why does the creature hate Victor?",
            "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive"},
            "chunk_text": "Victor felt a sudden hate for the creature that stood before him.",
            "distractors": [
                "The monster reached out his hand, seeking communion, but Victor shrank back in disgust.",
                "A dreadful silence fell between creator and creation upon the frozen glacier."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 9,
            "type": "Lexical overlap (Dracula)",
            "question": "Why does Dracula travel to London?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Dracula", "action": "travel to London", "polarity": "positive"},
            "chunk_text": "Jonathan looked at the map of London, while Dracula sat silently in the castle library in Transylvania.",
            "distractors": [
                "The library was filled with English books, newspapers, and directories.",
                "The Count questioned Harker closely on the manners and customs of English society."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # RELATIONSHIP REASONING (10-12)
        {
            "id": 10,
            "type": "Relationship false positive",
            "question": "Who is Victor's father?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
            "chunk_text": "Alphonse Frankenstein was a respected magistrate in Geneva. Victor studied science at Ingolstadt.",
            "distractors": [
                "The magistrate was held in high esteem by his fellow citizens for his public integrity.",
                "Victor had departed Geneva to pursue natural philosophy in Germany."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 11,
            "type": "Relationship true positive",
            "question": "Who is Victor's father?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
            "chunk_text": "My father, Alphonse Frankenstein, was respected by all who knew him, and watched over my childhood with immense tenderness.",
            "distractors": [
                "He filled several public situations with honour and reputation.",
                "My mother was Caroline Beaufort, daughter of his dearest friend."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 12,
            "type": "Relationship false positive (Harker)",
            "question": "Who is Mina's husband?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Mina", "target": "husband", "polarity": "positive"},
            "chunk_text": "Jonathan Harker admired Mina Murray's handwriting in her letters.",
            "distractors": [
                "She wrote with great precision and intelligence in her daily correspondence.",
                "Harker kept every note in his locked travelling desk."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # POLARITY & NEGATION (13-16)
        {
            "id": 13,
            "type": "Negation mismatch (Action happened)",
            "question": "Why doesn't Victor create a companion for the monster?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a companion for the monster", "polarity": "negative"},
            "chunk_text": "I agreed to the monster's demand and immediately began gathering materials to build a second creature.",
            "distractors": [
                "The monster promised to depart forever to the wilds of South America.",
                "I felt a heavy burden upon my soul as I acquiesced to his terrifying request."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 14,
            "type": "Negation mismatch (Action avoided)",
            "question": "Why does Victor create a female creature?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "positive"},
            "chunk_text": "I resolved never to complete the work, lest a race of devils be propagated upon the earth, and tore it to pieces.",
            "distractors": [
                "The howling fiend witnessed the destruction of his promised bride through the casement.",
                "I trampled the half-finished remains beneath my feet."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 15,
            "type": "Negation correct match",
            "question": "Why doesn't Victor create a female creature?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create a female creature", "polarity": "negative"},
            "chunk_text": "I shuddered to think that future generations might curse me as their pest, whose selfishness had not hesitated to buy its own peace at the price of the existence of the whole human race.",
            "distractors": [
                "They might even hate each other; the creature who already lived loathed his own deformity.",
                "She might refuse to comply with a compact made before her creation."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 16,
            "type": "Negation mismatch (Harker)",
            "question": "Why does Jonathan Harker stay at Castle Dracula?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "stay at Castle Dracula", "polarity": "positive"},
            "chunk_text": "I realized with a sinking heart that the castle was a prison, and I was a prisoner! Every door was bolted and locked.",
            "distractors": [
                "I wandered through the dark corridors seeking any passage of escape.",
                "The sheer drop from the castle window made descent impossible."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # TEMPORAL RELATION (17-19)
        {
            "id": 17,
            "type": "Temporal mismatch (Before/After)",
            "question": "What happens after Victor meets the monster on the glacier?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
            "chunk_text": "Before travelling to the glacier of Montanvert, Victor spent two weeks in Geneva mourning the death of William and Justine.",
            "distractors": [
                "His father urged him to take solace in the beauty of the surrounding valleys.",
                "He wandered like an evil spirit through the familiar scenes of his youth."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 18,
            "type": "Temporal correct match",
            "question": "What happens after Victor meets the monster on the glacier?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor meets the monster on the glacier", "temporal_relation": "AFTER", "polarity": "positive"},
            "chunk_text": "After hearing the creature's long tale inside the hut on the Mer de Glace, Victor reluctantly agreed to make him a companion.",
            "distractors": [
                "They descended the mountain separately under the darkening twilight sky.",
                "Victor returned to Geneva weighed down by the dreadful promise he had made."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 19,
            "type": "Temporal mismatch (Harker)",
            "question": "What does Harker do before entering Castle Dracula?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "entering Castle Dracula", "temporal_relation": "BEFORE", "polarity": "positive"},
            "chunk_text": "After entering the castle courtyard, Harker was greeted by a tall old man with a long white moustache.",
            "distractors": [
                "The Count bowed courteously and welcomed him to his dwelling.",
                "The heavy iron doors clanged shut behind the carriage."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # ACTOR / EVENT MISMATCH (20-22)
        {
            "id": 20,
            "type": "Actor mismatch (Dracula)",
            "question": "Why does Van Helsing want to destroy Dracula?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "destroy Dracula", "polarity": "positive"},
            "chunk_text": "Dracula wished to destroy the men who dared to meddle with his earth boxes.",
            "distractors": [
                "The Count swore vengeance upon the small band of companions.",
                "He stalked the streets of London seeking Mina Harker."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 21,
            "type": "Event mismatch (Victor)",
            "question": "Why did Victor travel to England with Henry Clerval?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "travel to England with Henry Clerval", "polarity": "positive"},
            "chunk_text": "Victor travelled to Ingolstadt alone to study chemistry and natural philosophy under Professor Waldman.",
            "distractors": [
                "His father had arranged his departure from Geneva two years earlier.",
                "He found lodging near the university gates."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 22,
            "type": "Actor mismatch (Creature)",
            "question": "Who saves the drowning girl in the river?",
            "intent_data": {"intent": "FACTUAL", "actor": "Creature", "action": "saves the drowning girl", "polarity": "positive"},
            "chunk_text": "A rustic hunter rushed forward and dragged the drowning girl from the rapid river current.",
            "distractors": [
                "The girl's father embraced the hunter with tears of gratitude.",
                "The monster watched from the thick foliage of the woods."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },

        # INTENT / REMORSE BOUNDARIES (23-25)
        {
            "id": 23,
            "type": "Intent mismatch (Regret vs Motivation)",
            "question": "Why does Victor feel remorse for his creation?",
            "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
            "chunk_text": "I was seized with a fierce determination to hunt the creature down and slaughter him upon the frozen northern wastes.",
            "distractors": [
                "No obstacle of ice or storm would stay my relentless pursuit.",
                "I vowed vengeance before the graves of my murdered family."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 24,
            "type": "Intent correct match (Regret)",
            "question": "Why does Victor feel remorse for his creation?",
            "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "feel remorse", "polarity": "positive"},
            "chunk_text": "A terrible sense of guilt overwhelmed me; I felt as if I had unleashed an unquenchable curse upon the innocent, and wept bitter tears of remorse.",
            "distractors": [
                "The memory of William and Justine haunted my sleepless nights.",
                "I looked upon myself as the true murderer of those I loved."
            ],
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 25,
            "type": "Intent mismatch (Reaction vs Consequence)",
            "question": "How does Victor react when the creature awakens?",
            "intent_data": {"intent": "REACTION", "actor": "Victor", "action": "react when creature awakens", "polarity": "positive"},
            "chunk_text": "Three months later, Victor received a letter from his father informing him of William's tragic death.",
            "distractors": [
                "The letter arrived on a cold autumn morning in Ingolstadt.",
                "Clerval observed the sudden pallor on his friend's face."
            ],
            "expected_verdict": "NOT_SUPPORTED"
        }
    ]

    modes = ["top-1", "top-3-ind", "top-3-comb"]
    ablation_results = {}

    for mode in modes:
        print(f"\n--- Running Validator Mode: {mode} ---")
        mode_records = []
        latencies = []
        fp_count = 0
        fn_count = 0
        correct_count = 0
        unsupported_total = sum(1 for c in cases if c["expected_verdict"] == "NOT_SUPPORTED")
        unsupported_detected = 0

        for c in cases:
            # Build used_items
            if mode == "top-1":
                used_items = [{"text": c["chunk_text"]}]
            else:
                used_items = [{"text": c["chunk_text"]}] + [{"text": d} for d in c.get("distractors", [])]

            t0 = time.perf_counter()

            if mode == "top-3-ind":
                # Validate each chunk independently, pass if ANY chunk is supported
                any_supported = False
                ind_details = []
                for item in used_items:
                    res = llm.validate_evidence(c["question"], c["intent_data"], [item], mode="top-1")
                    verdict = res.get("verdict", "NOT_SUPPORTED") if isinstance(res, dict) else res
                    ind_details.append(res)
                    if verdict == "SUPPORTED":
                        any_supported = True
                        break
                pred_verdict = "SUPPORTED" if any_supported else "NOT_SUPPORTED"
                details = ind_details[0].get("details", {}) if ind_details else {}
            else:
                res = llm.validate_evidence(c["question"], c["intent_data"], used_items, mode=mode)
                pred_verdict = res.get("verdict", "NOT_SUPPORTED") if isinstance(res, dict) else res
                details = res.get("details", {}) if isinstance(res, dict) else {}

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
                "latency_ms": round(lat_ms, 2),
                "details": details
            }
            mode_records.append(rec)
            status = "PASS" if is_correct else "FAIL"
            print(f"[{c['id']:02d}] {c['type'][:35]:<35} | Exp: {exp_verdict:<13} | Pred: {pred_verdict:<13} | {status} ({lat_ms:.1f}ms)")

        accuracy = (correct_count / len(cases)) * 100
        unsupported_rate = (unsupported_detected / unsupported_total) * 100 if unsupported_total else 0.0

        ablation_results[mode] = {
            "total_cases": len(cases),
            "correct_count": correct_count,
            "accuracy_percent": round(accuracy, 2),
            "false_positives": fp_count,
            "false_negatives": fn_count,
            "unsupported_premise_detection_percent": round(unsupported_rate, 2),
            "mean_latency_ms": round(float(np.mean(latencies)), 2),
            "median_latency_ms": round(float(np.median(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "records": mode_records
        }

        print(f"\n--> Summary for {mode}: Accuracy={accuracy:.1f}% | FP={fp_count} | FN={fn_count} | Unsupp={unsupported_rate:.1f}% | Latency(mean)={np.mean(latencies):.2f}ms\n")

    with open("eval_results_v6_validator_ablation.json", "w", encoding="utf-8") as f:
        json.dump(ablation_results, f, indent=2)

    print("\n[DONE] Validator ablation saved to eval_results_v6_validator_ablation.json")

if __name__ == "__main__":
    main()
