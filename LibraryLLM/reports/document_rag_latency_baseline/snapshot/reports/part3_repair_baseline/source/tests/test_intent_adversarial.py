import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from rag.llm import LuminaRLLM

@pytest.fixture(scope="module")
def llm():
    return LuminaRLLM()

def test_intent_adversarial_1(llm):
    # "Why does Victor fear creating another creature?" 
    # Should not be REGRET (has 'regret' in regex? No, 'fear' is not in regex).
    # Might trigger MOTIVATION ("why does Victor... create"). But it's actually NEGATED_MOTIVATION or MOTIVATION depending on interpretation.
    res = llm.analyze_intent("Why does Victor fear creating another creature?")
    # We just assert it doesn't crash and returns a valid intent
    assert res["intent"] in ["MOTIVATION", "NEGATED_MOTIVATION", "REACTION"]

def test_intent_adversarial_2(llm):
    # "Why does the creature not hate Victor?"
    # Contains "why does... not hate". Should be NEGATED_MOTIVATION or similar, but the regex `why doesn't` or `does not` followed by actor might fail here since actor is "the creature" and "not" comes after.
    res = llm.analyze_intent("Why does the creature not hate Victor?")
    assert res["intent"] in ["NEGATED_MOTIVATION", "MOTIVATION", "FACTUAL"]

def test_intent_adversarial_3(llm):
    # "What happens before Victor creates the creature?"
    # Contains "what happens", but "before" instead of "after".
    res = llm.analyze_intent("What happens before Victor creates the creature?")
    # Regex Tier 1 specifically looks for "after". This should fall back to LLM or FACTUAL.
    assert res["intent"] in ["FACTUAL", "CONSEQUENCE"]

def test_intent_adversarial_4(llm):
    # "What happens immediately after Victor first sees the creature?"
    # Collision between CONSEQUENCE ("what happens after") and REACTION ("when Victor first sees").
    res = llm.analyze_intent("What happens immediately after Victor first sees the creature?")
    assert res["intent"] in ["CONSEQUENCE", "REACTION"]

def test_intent_adversarial_5(llm):
    # "Why does Victor regret NOT destroying the creature?"
    # Polarity collision. Intent is REGRET, but the action is negated.
    res = llm.analyze_intent("Why does Victor regret NOT destroying the creature?")
    assert res["intent"] == "REGRET"

def test_intent_adversarial_6(llm):
    # "Who does Victor's father know?"
    # Contains "Who is... " wait, no "who does". Should be FACTUAL, not RELATIONSHIP.
    res = llm.analyze_intent("Who does Victor's father know?")
    assert res["intent"] == "FACTUAL"

def test_intent_adversarial_7(llm):
    # "Why doesn't the creature forgive Victor?"
    res = llm.analyze_intent("Why doesn't the creature forgive Victor?")
    assert res["intent"] == "NEGATED_MOTIVATION"
    assert res["polarity"] == "negative"

def test_intent_adversarial_8(llm):
    # "Does Dracula regret attacking his victims?"
    # "Does" instead of "Why does". Should be FACTUAL or REGRET?
    res = llm.analyze_intent("Does Dracula regret attacking his victims?")
    assert res["intent"] in ["FACTUAL", "REGRET"]

def test_intent_adversarial_9(llm):
    # "Why might Jonathan have wanted to leave the castle?"
    res = llm.analyze_intent("Why might Jonathan have wanted to leave the castle?")
    assert res["intent"] == "MOTIVATION"
