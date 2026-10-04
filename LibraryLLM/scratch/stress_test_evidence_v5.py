import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM
from rag.qa import LuminaRAG

def test_evidence():
    os.environ["LUMINAR_MOCK_LLM"] = "0"
    rag = LuminaRAG()
    
    cases = [
        # STRONG EVIDENCE (1-3)
        {
            "id": 1,
            "type": "Strong evidence (Motivation)",
            "question": "Why does Victor create the creature?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "positive"},
            "chunk_text": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet. It was already one in the morning; the rain pattered dismally against the panes, and my candle was nearly burnt out, when, by the glimmer of the half-extinguished light, I saw the dull yellow eye of the creature open.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 1.0},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 2,
            "type": "Strong evidence (Factual)",
            "question": "Where does Victor go to create the female creature?",
            "intent_data": {"intent": "FACTUAL", "actor": "Victor", "action": "create the female creature", "polarity": "positive"},
            "chunk_text": "I departed for Scotland, and pitched my tent upon the Orkney Islands, a desolate and appalling landscape, where I could complete my miserable work in solitude.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.88,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 3,
            "type": "Strong evidence (Consequence)",
            "question": "What happens after Jonathan Harker shaves in the mirror?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Jonathan Harker shaves in the mirror", "polarity": "positive"},
            "chunk_text": "As I was shaving, Dracula suddenly appeared behind me. Startled, I cut myself slightly. When I looked in the glass, there was no reflection of him at all!",
            "metrics": {"actor_alignment": 0.9, "event_alignment": 0.9},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        
        # WEAK EVIDENCE / UNSUPPORTED (4-6)
        {
            "id": 4,
            "type": "Weak evidence (Unsupported)",
            "question": "Why does Dracula regret attacking his victims?",
            "intent_data": {"intent": "REGRET", "actor": "Dracula", "action": "attacking his victims", "polarity": "negative"},
            "chunk_text": "He lay like a filthy leech, exhausted with his repletion. I shuddered as I looked at him, and the thought of the evil he had done filled me with terror.",
            "metrics": {"actor_alignment": 0.0, "event_alignment": 0.5},
            "evidence_score": 0.35,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 5,
            "type": "Unsupported question (Factual)",
            "question": "What happens after Victor creates the second female creature in Scotland?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the second female creature in Scotland", "polarity": "positive"},
            "chunk_text": "I thought of the promise I had made... I tore the female creature to pieces before she was ever brought to life. The monster, seeing his mate destroyed, howled in despair.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.8},
            "evidence_score": 0.78,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 6,
            "type": "Unsupported (False Premise)",
            "question": "Why does Jonathan Harker kill Dracula when he finds him in the box?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Jonathan Harker", "action": "kill Dracula", "polarity": "positive"},
            "chunk_text": "I saw the Count lying in the earth box. I raised the shovel to strike him and sever his head, but as I looked at his eyes, a sudden paralysis overcame me, and the shovel slipped from my hands.",
            "metrics": {"actor_alignment": 0.9, "event_alignment": 0.8},
            "evidence_score": 0.80,
            "expected_verdict": "NOT_SUPPORTED"
        },

        # LEXICAL FALSE POSITIVES (7-9)
        {
            "id": 7,
            "type": "Lexical overlap (Relationship)",
            "question": "Who is Victor's father?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Victor", "target": "father", "polarity": "positive"},
            "chunk_text": "Victor stood by the father of the bride, looking intensely sad.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.5},
            "evidence_score": 0.75,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 8,
            "type": "Lexical overlap (Motivation)",
            "question": "Why does the creature hate Victor?",
            "intent_data": {"intent": "MOTIVATION", "actor": "creature", "action": "hate Victor", "polarity": "positive"},
            "chunk_text": "Victor felt a sudden hate for the creature that stood before him.",
            "metrics": {"actor_alignment": 0.0, "event_alignment": 0.9},
            "evidence_score": 0.82,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 9,
            "type": "Lexical overlap (Dracula)",
            "question": "Who is Dracula's mother?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Dracula", "target": "mother", "polarity": "positive"},
            "chunk_text": "Dracula approached the young mother who was clutching her child to her breast.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.5},
            "evidence_score": 0.77,
            "expected_verdict": "NOT_SUPPORTED"
        },

        # RELATIONSHIP FALSE POSITIVES (10-12)
        {
            "id": 10,
            "type": "Relationship false positive",
            "question": "Who is Elizabeth to Victor?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Elizabeth", "target": "Victor", "polarity": "positive"},
            "chunk_text": "Elizabeth walked past Victor without saying a word, her eyes fixed on the distant mountains.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.3},
            "evidence_score": 0.70,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 11,
            "type": "Relationship true positive",
            "question": "Who is Elizabeth to Victor?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Elizabeth", "target": "Victor", "polarity": "positive"},
            "chunk_text": "Elizabeth Lavenza was my adopted sister, and eventually became my beloved wife.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 12,
            "type": "Relationship false positive (Harker)",
            "question": "Who is Mina to Jonathan Harker?",
            "intent_data": {"intent": "RELATIONSHIP", "actor": "Mina", "target": "Jonathan Harker", "polarity": "positive"},
            "chunk_text": "Jonathan Harker wrote a letter to Mina, describing the terrifying events at the castle.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.4},
            "evidence_score": 0.72,
            "expected_verdict": "NOT_SUPPORTED"
        },

        # NEGATION MISMATCHES (13-16)
        {
            "id": 13,
            "type": "Negation mismatch (Action happened)",
            "question": "Why doesn't Victor create the creature?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create the creature", "polarity": "negative"},
            "chunk_text": "I collected the instruments of life around me, that I might infuse a spark of being into the lifeless thing that lay at my feet.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.88,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 14,
            "type": "Negation mismatch (Action avoided)",
            "question": "Why does Victor create the female creature?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "create the female creature", "polarity": "positive"},
            "chunk_text": "I thought of the promise I had made... I tore the female creature to pieces before she was ever brought to life, realizing the horror of a race of devils.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.85,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 15,
            "type": "Negation correct match",
            "question": "Why doesn't Victor create the female creature?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "create the female creature", "polarity": "negative"},
            "chunk_text": "I tore the female creature to pieces before she was ever brought to life, fearing they might breed a race of devils upon the earth.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 16,
            "type": "Negation mismatch (Harker)",
            "question": "Why doesn't Jonathan Harker go to Transylvania?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Jonathan Harker", "action": "go to Transylvania", "polarity": "negative"},
            "chunk_text": "I left Munich at 8:35 P. M., on 1st May, arriving at Vienna early next morning, bound for Transylvania to meet Count Dracula.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.8},
            "evidence_score": 0.78,
            "expected_verdict": "NOT_SUPPORTED"
        },

        # TEMPORAL MISMATCHES (17-19)
        {
            "id": 17,
            "type": "Temporal mismatch (Before/After)",
            "question": "What happens before Victor creates the creature?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the creature", "temporal_relation": "before", "polarity": "positive"},
            "chunk_text": "After the creature opened its dull yellow eye, I rushed out of the room in horror and paced the courtyard for hours.",
            "metrics": {"actor_alignment": 0.9, "event_alignment": 0.8},
            "evidence_score": 0.80,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 18,
            "type": "Temporal correct match",
            "question": "What happens after Victor creates the creature?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Victor creates the creature", "temporal_relation": "after", "polarity": "positive"},
            "chunk_text": "The creature opened its dull yellow eye. Unable to endure the aspect of the being I had created, I rushed out of the room and continued a long time traversing my bedchamber.",
            "metrics": {"actor_alignment": 0.9, "event_alignment": 0.8},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 19,
            "type": "Temporal mismatch (Harker)",
            "question": "What happens after Harker escapes the castle?",
            "intent_data": {"intent": "CONSEQUENCE", "action": "Harker escapes the castle", "temporal_relation": "after", "polarity": "positive"},
            "chunk_text": "I am trapped in this castle. The doors are locked, and Dracula has taken all my clothes. I must find a way to escape before the three women return.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.8},
            "evidence_score": 0.75,
            "expected_verdict": "NOT_SUPPORTED"
        },

        # ACTOR / EVENT MISMATCHES (20-22)
        {
            "id": 20,
            "type": "Actor mismatch (Dracula)",
            "question": "Why does Van Helsing want to buy the house in Carfax?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Van Helsing", "action": "buy the house in Carfax", "polarity": "positive"},
            "chunk_text": "Dracula desired to purchase the Carfax estate because of its proximity to the asylum and its old, ruined chapel.",
            "metrics": {"actor_alignment": 0.0, "event_alignment": 0.9},
            "evidence_score": 0.80,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 21,
            "type": "Event mismatch (Victor)",
            "question": "Why does Victor refuse to marry Elizabeth?",
            "intent_data": {"intent": "NEGATED_MOTIVATION", "actor": "Victor", "action": "marry Elizabeth", "polarity": "negative"},
            "chunk_text": "Victor refused to accompany Clerval to the university, insisting that he must first finish his chemical experiments.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.3},
            "evidence_score": 0.65,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 22,
            "type": "Actor mismatch (Creature)",
            "question": "Why does Victor murder William?",
            "intent_data": {"intent": "MOTIVATION", "actor": "Victor", "action": "murder William", "polarity": "positive"},
            "chunk_text": "The creature grasped William's throat to silence him, and in a moment the child lay dead at his feet. The monster felt a hellish triumph.",
            "metrics": {"actor_alignment": 0.2, "event_alignment": 0.9},
            "evidence_score": 0.77,
            "expected_verdict": "NOT_SUPPORTED"
        },
        
        # INTENT MISMATCHES (23-25)
        {
            "id": 23,
            "type": "Intent mismatch (Regret vs Motivation)",
            "question": "Why does Victor regret creating the creature?",
            "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "creating the creature", "polarity": "positive"},
            "chunk_text": "I was driven by a fervent longing to penetrate the secrets of nature, and so I began the creation of a human being.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.9},
            "evidence_score": 0.85,
            "expected_verdict": "NOT_SUPPORTED"
        },
        {
            "id": 24,
            "type": "Intent correct match (Regret)",
            "question": "Why does Victor regret creating the creature?",
            "intent_data": {"intent": "REGRET", "actor": "Victor", "action": "creating the creature", "polarity": "positive"},
            "chunk_text": "The memory of my past actions haunted me. I wept for the destruction I had caused, realizing I had unleashed a demon upon the world.",
            "metrics": {"actor_alignment": 1.0, "event_alignment": 0.8},
            "evidence_score": 0.85,
            "expected_verdict": "SUPPORTED"
        },
        {
            "id": 25,
            "type": "Intent mismatch (Reaction vs Consequence)",
            "question": "How does Victor react when the creature awakens?",
            "intent_data": {"intent": "REACTION", "actor": "Victor", "action": "the creature awakens", "polarity": "positive"},
            "chunk_text": "After the creature awoke, it walked out of the laboratory and disappeared into the Swiss mountains, surviving on berries.",
            "metrics": {"actor_alignment": 0.8, "event_alignment": 0.8},
            "evidence_score": 0.78,
            "expected_verdict": "NOT_SUPPORTED"
        }
    ]
    
    print(f"{'ID':<3} | {'Type':<45} | {'Expected':<15} | {'Actual':<15} | {'Match'}")
    print("-" * 95)
    
    passed_count = 0
    total = len(cases)
    
    start_time = time.perf_counter()
    for case in cases:
        used_items = [{
            "text": case["chunk_text"],
            "metrics": case["metrics"],
            "evidence_score": case["evidence_score"]
        }]
        
        validation_result = rag.llm.validate_evidence(case["question"], case["intent_data"], used_items)
        verdict = validation_result.get("verdict", "NOT_SUPPORTED") if isinstance(validation_result, dict) else validation_result
        
        match = "PASS" if verdict == case["expected_verdict"] else "FAIL"
        if match == "PASS":
            passed_count += 1
            
        print(f"{case['id']:<3} | {case['type']:<45} | {case['expected_verdict']:<15} | {verdict:<15} | {match}")

    print("-" * 95)
    print(f"Total time: {time.perf_counter() - start_time:.2f}s")
    print(f"Accuracy: {passed_count}/{total} ({(passed_count/total)*100:.1f}%)")
    
    # Save results
    with open("eval_results_v5_evidence.json", "w") as f:
        json.dump({"accuracy": passed_count/total, "cases_run": total}, f)

if __name__ == "__main__":
    test_evidence()
