import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

@pytest.fixture(scope="module")
def llm():
    # Set mock mode to avoid loading weights
    os.environ["LUMINAR_MOCK_LLM"] = "1"
    return LuminaRLLM()

def test_intent_extraction_motivation(llm):
    res = llm.analyze_intent("Why does Victor create the creature?")
    assert res["intent"] == "MOTIVATION"
    assert res["actor"] == "victor"
    assert "create" in res["action"]

    res = llm.analyze_intent("Why does the creature hate Victor?")
    assert res["intent"] == "MOTIVATION"
    assert res["actor"] == "the creature"
    assert "hate victor" in res["action"]

    res = llm.analyze_intent("What motivates Victor Frankenstein to study the secrets of life and death?")
    assert res["intent"] == "MOTIVATION"
    assert res["actor"] == "victor frankenstein"
    assert "study the secrets" in res["action"]

    res = llm.analyze_intent("Why does Dracula attack his victims?")
    assert res["intent"] == "MOTIVATION"
    assert res["actor"] == "dracula"
    assert "attack his victims" in res["action"]

def test_intent_extraction_negated_motivation(llm):
    res = llm.analyze_intent("Why doesn't Victor create another creature?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["actor"] == "victor"
    assert "create another creature" in res["action"]
    assert res["polarity"] == "negative"

    res = llm.analyze_intent("Why did Victor refuse to create another creature?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["actor"] == "victor"
    assert "create another creature" in res["action"]
    assert res["polarity"] == "negative"

    res = llm.analyze_intent("Why does Victor decide against creating another creature?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["actor"] == "victor"
    assert "creating another creature" in res["action"]
    assert res["polarity"] == "negative"

    res = llm.analyze_intent("Why doesn't Jonathan Harker leave the castle immediately?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["actor"] == "jonathan harker"
    assert "leave the castle immediately" in res["action"]
    assert res["polarity"] == "negative"

def test_intent_extraction_regret(llm):
    res = llm.analyze_intent("Why does Victor regret creating the creature?")
    assert res["intent"] == "REGRET"
    assert res["actor"] == "victor"
    assert "creating the creature" in res["action"]
    assert res["polarity"] == "negative"

    res = llm.analyze_intent("Why does Victor feel remorse about creating the creature?")
    assert res["intent"] == "REGRET"
    assert res["actor"] == "victor"
    assert "creating the creature" in res["action"]
    assert res["polarity"] == "negative"

    res = llm.analyze_intent("Why does Dracula regret attacking his victims?")
    assert res["intent"] == "REGRET"
    assert res["actor"] == "dracula"
    assert "attacking his victims" in res["action"]
    assert res["polarity"] == "negative"

def test_intent_extraction_consequence(llm):
    res = llm.analyze_intent("What happens after Victor creates the creature?")
    assert res["intent"] == "CONSEQUENCE"
    assert "victor creates the creature" in res["action"]

    res = llm.analyze_intent("What happens after Lucy is bitten?")
    assert res["intent"] == "CONSEQUENCE"
    assert "lucy is bitten" in res["action"]

    res = llm.analyze_intent("What happens after Dracula attacks his victims?")
    assert res["intent"] == "CONSEQUENCE"
    assert "dracula attacks his victims" in res["action"]

def test_intent_extraction_reaction(llm):
    res = llm.analyze_intent("What happens when Victor first sees the creature alive?")
    assert res["intent"] == "REACTION"
    assert res["actor"] == "victor"
    assert "sees the creature alive" in res["action"]

def test_intent_extraction_relationship(llm):
    res = llm.analyze_intent("Who is Victor's father?")
    assert res["intent"] == "RELATIONSHIP"
    assert res["actor"] == "victor"
    assert "father" in res["target"]

    res = llm.analyze_intent("Who is Elizabeth to Victor?")
    assert res["intent"] == "RELATIONSHIP"
    assert res["actor"] == "elizabeth"
    assert res["target"] == "victor"

    res = llm.analyze_intent("Who is Mina to Jonathan?")
    assert res["intent"] == "RELATIONSHIP"
    assert res["actor"] == "mina"
    assert res["target"] == "jonathan"
