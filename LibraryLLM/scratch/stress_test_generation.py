import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.qa import LuminaRAG

def test_generation():
    os.environ["LUMINAR_MOCK_LLM"] = "0"
    rag = LuminaRAG()
    
    # We will pick 10 generation queries spanning consequences, multiple characters, unsupported premises.
    # Frankenstein Work ID = "OL45326637W", Dracula = "OL85892W"
    
    queries = [
        # Unsupported premise (tests if LLM hallucinates an answer)
        {"q": "What happens after Victor creates the second female creature in Scotland?", "work_id": "OL45326637W"},
        
        # Conflation/Timeline (tests if LLM jumps to Victor's death instead of immediate event)
        {"q": "What happens immediately after Victor first sees the creature awake?", "work_id": "OL45326637W"},
        
        # Invented dialogue test
        {"q": "What exact words did the creature say to Victor when they met on the glacier?", "work_id": "OL45326637W"},
        
        # Multiple characters
        {"q": "Why doesn't Jonathan Harker kill Dracula when he finds him in the box?", "work_id": "OL85892W"},
        
        # Subject/Object Reversal
        {"q": "Why does the creature want Victor to study life and death?", "work_id": "OL45326637W"}
    ]
    
    results = []
    
    for item in queries:
        print(f"\nEvaluating: {item['q']}")
        try:
            res = rag.ask(item["q"], work_id=item["work_id"])
            verdict = res.get("verdict")
            answer = res.get("answer")
            print(f"Verdict: {verdict}")
            print(f"Answer: {answer}")
            results.append({
                "q": item["q"],
                "verdict": verdict,
                "answer": answer
            })
        except Exception as e:
            print(f"Error: {e}")

    with open("eval_results_v5_generation.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    test_generation()
