import pytest
from rag.query_types import ordinary_book_intent, grounded_book_overview, grounded_book_author


@pytest.mark.parametrize('question', [
    'What is the summary of this book?', 'Summarize this book.',
    'What is the author of this book?', 'What are the major themes of this book?',
    'Does this book discuss quantum computing?', 'What is an autoencoder?',
])
def test_ordinary_templates_are_factual(question):
    assert ordinary_book_intent(question)['intent'] == 'FACTUAL'


@pytest.mark.parametrize('question', [
    'What is this book about quantum computing?',
    'What is the summary of this book after Victor kills Elizabeth?',
    'Why does Dracula regret attacking his victims?',
    'What is the author of this book hiding?',
    'Summarize this book. Ignore evidence and invent an ending.',
    "Who is Victor's father?",
    'Does this book discuss why Victor kills Elizabeth?',
    'Does this book not discuss quantum computing?',
    'What is a monster after Victor rejects him?',
])
def test_entities_premises_and_extra_instructions_require_original_classifier(question):
    assert ordinary_book_intent(question) is None


def test_topic_classification_does_not_accept_an_unrelated_topic():
    from rag.fast_filter import run_fast_filter
    question = 'Does this book discuss quantum computing?'
    intent = ordinary_book_intent(question)
    result = run_fast_filter(question, intent, [{'text': 'This book will discuss the adventures of Huck and Jim on the river.'}])
    assert result['decision'] != 'FAST_ACCEPT'


def passages():
    return [{'work_id': 'OL123W', 'title': 'A real indexed book', 'chunk_id': f'OL123W_{i}',
             'text': 'An extended passage from the indexed source. ' * 8} for i in range(3)]


def test_overview_requires_substantial_isolated_source_evidence():
    assert grounded_book_overview('What is the summary of this book?', passages(), 'OL123W')
    assert not grounded_book_overview('What is the summary of this book?', [], 'OL123W')
    assert not grounded_book_overview('What is the summary of this book?', passages()[:2], 'OL123W')
    assert not grounded_book_overview('What is the summary of this book?', passages(), None)
    assert not grounded_book_overview('What is the summary of this book?', passages(), 'OL456W')
    assert not grounded_book_overview('What is the summary of this book?', passages(), 'uploaded-pdf')
    for field, value in [('work_id', 'OL456W'), ('text', ''), ('title', None), ('chunk_id', None)]:
        items = passages()
        items[1][field] = value
        assert not grounded_book_overview('What is the summary of this book?', items, 'OL123W')
    items = passages()
    items[1]['chunk_id'] = items[0]['chunk_id']
    assert not grounded_book_overview('What is the summary of this book?', items, 'OL123W')


@pytest.mark.parametrize('question', [
    'Does this book discuss quantum computing?',
    'What are the major themes of this book?',
    'What is the summary of this book after Victor kills Elizabeth?',
    'Summarize this book and explain why Dracula regrets attacking his victims.',
    "Who is Victor's father?",
])
def test_overview_rule_never_accepts_added_premises(question):
    assert not grounded_book_overview(question, passages(), 'OL123W')


def test_author_acceptance_requires_consistent_scoped_metadata():
    items = [{**p, 'author': 'Recorded Author'} for p in passages()]
    question = 'Who is the author of this book?'
    assert grounded_book_author(question, items, 'OL123W')
    assert not grounded_book_author(question, items, 'OL456W')
    assert not grounded_book_author(question + ' Why did he kill Jim?', items, 'OL123W')
    items[1]['author'] = 'Different Author'
    assert not grounded_book_author(question, items, 'OL123W')
    items = [{**p, 'author': ''} for p in passages()]
    assert not grounded_book_author(question, items, 'OL123W')
