"""Gold-labelled final-answer checks through the existing LuminaRAG.ask path."""
import pytest

from tests.test_urgent_document_rag import candidate, fake_engine, FLOW_DEFINITION


@pytest.mark.parametrize("answer,verdict,cited", [
    ("No.", "NOT_SUPPORTED", False),
    ("Yes.", "SUPPORTED", True),
    ("61 minutes is 3660 seconds.", "SUPPORTED", True),
    ("They are equivalent.", "SUPPORTED", True),
    ("I cannot verify that.", "NOT_SUPPORTED", False),
    ("It is probably so.", "NOT_SUPPORTED", False),
    ("61 minutes is 3600 seconds.", "NOT_SUPPORTED", False),
])
def test_final_answer_precedes_citation_entitlement(monkeypatch, answer, verdict, cited):
    own = candidate("own", "61 minutes equals 3660 seconds.", 1)
    engine, _, _ = fake_engine(monkeypatch, [own], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: answer
    result = engine.ask("Does 61 minutes equal 3660 seconds?", document_id="selected-doc")
    assert result["verdict"] == verdict
    assert bool(result["sources"]) is cited
    if cited:
        assert result["answer"] == answer
        assert [source["chunk_id"] for source in result["sources"]] == ["own"]
    elif answer == "No.":
        assert result["answer"] != answer


def test_private_code_answer_stays_supported_without_rewriting(monkeypatch):
    own = candidate("own", "The calibration code is BRAVO-NINE. Routine checks take 47 minutes.", 1)
    engine, _, _ = fake_engine(monkeypatch, [own], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: "BRAVO-NINE"
    result = engine.ask("What calibration code is recorded?", document_id="selected-doc")
    assert result["verdict"] == "SUPPORTED"
    assert result["answer"] == "BRAVO-NINE"
    assert [source["chunk_id"] for source in result["sources"]] == ["own"]


def test_unknown_explicit_code_answer_abstains(monkeypatch):
    own = candidate("own", "The calibration code is BRAVO-NINE.", 1)
    engine, _, _ = fake_engine(monkeypatch, [own], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: "It might be BRAVO-NINE."
    result = engine.ask("What calibration code is recorded?", document_id="selected-doc")
    assert result["verdict"] == "NOT_SUPPORTED"
    assert result["sources"] == []


def test_document_definition_outside_bounded_fact_scope(monkeypatch):
    engine, validations, _ = fake_engine(monkeypatch, [candidate("definition", FLOW_DEFINITION, 1)])
    result = engine.ask("what is flow control", document_id="selected-doc")
    assert len(validations) == 1
    assert result["verdict"] == "SUPPORTED"
    assert result["answer"] == FLOW_DEFINITION
    assert [source["chunk_id"] for source in result["sources"]] == ["definition"]


def test_wrong_source_never_reaches_generation(monkeypatch):
    foreign = candidate("foreign", "The calibration code is VELA-27.", 1, document_id="foreign-doc")
    engine, _, generated = fake_engine(monkeypatch, [foreign], verdict="SUPPORTED")
    result = engine.ask("What calibration code is recorded?", document_id="selected-doc")
    assert generated == []
    assert result["sources"] == []


def test_http_adapter_cannot_restore_a_false_support_citation(monkeypatch):
    from tests.institution_v2q_ai.test_v2q1c_citations import adapted
    own = candidate("own", "61 minutes equals 3660 seconds.", 1)
    engine, _, _ = fake_engine(monkeypatch, [own], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: "No."
    question = "Does 61 minutes equal 3660 seconds?"
    result = adapted(engine.ask(question, document_id="selected-doc"), question)
    assert result["verdict"] == "NOT_SUPPORTED"
    assert result["sources"] == []
    assert result["answer"] != "No."


def test_two_selected_citations_support_two_explicit_claims(monkeypatch):
    chunks = [candidate("code", "Gauge access code is VELA-27.", 1),
              candidate("runtime", "Gauge runtime is 9 minutes.", 2)]
    engine, _, _ = fake_engine(monkeypatch, chunks, verdict="SUPPORTED")
    answer = "Gauge access code is VELA-27. Gauge runtime is 9 minutes."
    engine.llm.generate = lambda *a, **k: answer
    result = engine.ask("What is gauge access code?", document_id="selected-doc")
    assert result["verdict"] == "SUPPORTED"
    assert result["answer"] == answer
    assert {item["chunk_id"] for item in result["sources"]} == {"code", "runtime"}


def test_freeform_document_summary_retains_existing_path(monkeypatch):
    text = "The first section describes the protocol. The second compares two approaches."
    engine, _, _ = fake_engine(monkeypatch, [candidate("summary", text, 1)], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: "The document compares two approaches to the protocol."
    result = engine.ask("Summarize the document", document_id="selected-doc")
    assert result["verdict"] == "SUPPORTED"
    assert result["answer"] == "The document compares two approaches to the protocol."
    assert [source["chunk_id"] for source in result["sources"]] == ["summary"]


@pytest.mark.parametrize("answer", ["Yes.", "Yes, gauge access code is not VELA-27."])
def test_explicit_negative_fact_keeps_authorized_citation(monkeypatch, answer):
    own = candidate("own", "Gauge access code is not VELA-27.", 1)
    engine, _, _ = fake_engine(monkeypatch, [own], verdict="SUPPORTED")
    engine.llm.generate = lambda *a, **k: answer
    result = engine.ask("Is gauge access code not VELA-27?", document_id="selected-doc")
    assert result["verdict"] == "SUPPORTED"
    assert result["answer"] == answer
    assert [source["chunk_id"] for source in result["sources"]] == ["own"]
