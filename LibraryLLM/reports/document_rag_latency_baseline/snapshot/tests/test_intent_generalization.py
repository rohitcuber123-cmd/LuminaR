import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

@pytest.fixture(scope="module")
def llm():
    # Will use the LLM mode dictated by the environment variable
    return LuminaRLLM()

def test_intent_generalization_motivation(llm):
    # Q1: "Why does Victor create the creature?"
    res = llm.analyze_intent("What drives Victor to bring the creature to life?")
    assert res["intent"] == "MOTIVATION"
    assert res["actor"] in ["victor", "victor frankenstein", None] # LLM might output None or variations if Tier 1 misses

    res = llm.analyze_intent("For what reason did Victor construct the monster?")
    assert res["intent"] == "MOTIVATION"
    
    # Q11: "Why does the creature hate Victor?"
    res = llm.analyze_intent("What causes the creature to despise Victor?")
    assert res["intent"] == "MOTIVATION"
    
    res = llm.analyze_intent("Why is the creature so angry at Victor Frankenstein?")
    assert res["intent"] == "MOTIVATION"
    
    # Q12: "What motivates Victor Frankenstein to study the secrets of life and death?"
    res = llm.analyze_intent("Why did Victor Frankenstein begin researching life and death?")
    assert res["intent"] == "MOTIVATION"

    res = llm.analyze_intent("What compelled Victor to investigate the spark of being?")
    assert res["intent"] == "MOTIVATION"
    
    # Q13: "Why does Dracula attack his victims?"
    res = llm.analyze_intent("What is Dracula's reason for preying on his victims?")
    assert res["intent"] == "MOTIVATION"

    res = llm.analyze_intent("For what purpose does Dracula bite people?")
    assert res["intent"] == "MOTIVATION"

def test_intent_generalization_negated_motivation(llm):
    # Q2: "Why doesn't Victor create another creature?"
    res = llm.analyze_intent("What prevents Victor from making a second creature?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["polarity"] == "negative"

    # Q3: "Why did Victor refuse to create another creature?"
    res = llm.analyze_intent("For what reason did Victor say no to building a mate?")
    assert res["intent"] == "NEGATED_MOTIVATION"

    # Q4: "Why does Victor decide against creating another creature?"
    res = llm.analyze_intent("What made Victor change his mind about making a companion?")
    assert res["intent"] in ["NEGATED_MOTIVATION", "MOTIVATION"] # Depending on LLM interpretation

    # Q14: "Why doesn't Jonathan Harker leave the castle immediately?"
    res = llm.analyze_intent("What is stopping Harker from escaping the castle?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    
    res = llm.analyze_intent("Why did Jonathan Harker stay in the castle instead of leaving?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    
def test_intent_generalization_regret(llm):
    # Q5: "Why does Victor regret creating the creature?"
    res = llm.analyze_intent("What makes Victor remorseful about his creation?")
    assert res["intent"] == "REGRET"
    
    res = llm.analyze_intent("Why does Victor feel guilty for animating the monster?")
    assert res["intent"] == "REGRET"

    # Q6: "Why does Victor feel remorse about creating the creature?"
    res = llm.analyze_intent("What is the source of Victor's sorrow over his experiment?")
    assert res["intent"] == "REGRET"
    
    # Q17: "Why does Dracula regret attacking his victims?"
    res = llm.analyze_intent("Does Dracula ever feel bad about hurting people?")
    assert res["intent"] == "REGRET"

def test_intent_generalization_consequence(llm):
    # Q7: "What happens after Victor creates the creature?"
    res = llm.analyze_intent("What immediately follows the creature's creation?")
    assert res["intent"] == "CONSEQUENCE"
    
    res = llm.analyze_intent("Once the creature is alive, what does Victor do?")
    assert res["intent"] == "CONSEQUENCE"

    # Q15: "What happens after Lucy is bitten?"
    res = llm.analyze_intent("What events unfold once Lucy gets bitten by Dracula?")
    assert res["intent"] == "CONSEQUENCE"

    # Q18: "What happens after Dracula attacks his victims?"
    res = llm.analyze_intent("What is the result of Dracula feeding on someone?")
    assert res["intent"] == "CONSEQUENCE"

def test_intent_generalization_reaction(llm):
    # Q8: "What happens when Victor first sees the creature alive?"
    res = llm.analyze_intent("How does Victor react upon witnessing the creature awaken?")
    assert res["intent"] == "REACTION"

    res = llm.analyze_intent("What is Victor's immediate response to seeing the monster breathe?")
    assert res["intent"] == "REACTION"
    
def test_intent_generalization_relationship(llm):
    # Q9: "Who is Victor's father?"
    res = llm.analyze_intent("Who is Alphonse in relation to Victor?")
    assert res["intent"] in ["RELATIONSHIP", "FACTUAL"]

    res = llm.analyze_intent("Can you tell me the name of Victor Frankenstein's dad?")
    assert res["intent"] in ["RELATIONSHIP", "FACTUAL"]

    # Q10: "Who is Elizabeth to Victor?"
    res = llm.analyze_intent("How are Elizabeth and Victor related?")
    assert res["intent"] == "RELATIONSHIP"

    res = llm.analyze_intent("What is the connection between Victor and Elizabeth?")
    assert res["intent"] == "RELATIONSHIP"

    # Q16: "Who is Mina to Jonathan?"
    res = llm.analyze_intent("What is Mina's relationship with Jonathan Harker?")
    assert res["intent"] == "RELATIONSHIP"
    
    res = llm.analyze_intent("Are Mina and Jonathan married?")
    assert res["intent"] in ["RELATIONSHIP", "FACTUAL"]
