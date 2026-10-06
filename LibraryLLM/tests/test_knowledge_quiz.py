import ast
from itertools import combinations
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from rag.services import knowledge_algorithms as a
from rag.services import knowledge_quiz as q

FIXTURE = Path(__file__).parent/'fixtures/quiz_study.json'


def chunks():
    return json.loads(FIXTURE.read_text())


def generate(types, count=12, data=None):
    return a.generate('QUIZ', chunks() if data is None else data, 'Study', q.quiz_options(types, count))


SELECTIONS = [list(items) for size in range(1, 4) for items in combinations(q.QUESTION_TYPES, size)]


@pytest.mark.parametrize('selection', SELECTIONS)
def test_every_selection_is_respected_and_balanced(selection):
    result = generate(selection)
    types = [item['type'] for item in result['questions']]
    assert set(types) == set(selection)
    assert len(types) <= 12 and len(types) > 0
    assert result['generatedCounts'] == {kind: types.count(kind) for kind in sorted(selection)}
    if len(selection) == 3:
        assert max(types.count(kind) for kind in selection)-min(types.count(kind) for kind in selection) <= 1
    assert result == generate(list(reversed(selection)))


def test_mcq_unique_category_compatible_options_and_rotated_answers():
    result = generate(['mcq'])['questions']
    facts = {fact['concept']: fact for fact in q.reliable_facts(a.sentences(chunks()))}
    positions = set()
    for question in result:
        assert len(question['options']) == len(set(question['options'])) == 4
        assert question['options'].count(question['correctAnswer']) == 1
        positions.add(question['options'].index(question['correctAnswer']))
        assert len({facts[option]['category'] for option in question['options']}) == 1
        assert question['sourceChunkIds'] and question['pageStart']
        assert question['sourceExcerpt'] in next(c['text'] for c in chunks() if c['chunk_id'] == question['sourceChunkIds'][0])
        assert all(question['optionSources'][option]['sourceChunkIds'] for option in question['options'])
    assert len(positions) > 1


def test_insufficient_distractors_skip_mcqs_without_unselected_fallback():
    assert generate(['mcq'], data=chunks()[:1])['questions']  # Four explicit scheduling algorithms.
    little = [{'chunk_id':'c1', 'text':'Virtual memory is a memory-management technique that extends apparent memory with secondary storage.'}]
    result = generate(['mcq'], data=little)
    assert result['questions'] == [] and result['messages']
    mixed = generate(['mcq', 'fill_blank'], data=little)
    assert {item['type'] for item in mixed['questions']} == {'fill_blank'}
    assert mixed['generatedCounts']['mcq'] == 0 and mixed['messages']


def test_matching_unique_structured_pairs_shuffled_and_grounded():
    result = generate(['matching'])['questions']
    assert result
    for question in result:
        left, right, mapping = question['leftItems'], question['rightItems'], question['correctMatches']
        assert 3 <= len(left) == len(right) <= 5
        assert len({item['text'] for item in left}) == len(left)
        assert len({item['text'] for item in right}) == len(right)
        assert set(mapping) == {item['id'] for item in left}
        assert set(mapping.values()) == {item['id'] for item in right}
        assert [mapping[item['id']] for item in left] != [item['id'] for item in right]
        for item in left:
            assert item['sourceChunkIds'] and item['sourceExcerpt']
            source = next(c for c in chunks() if c['chunk_id'] == item['sourceChunkIds'][0])
            assert item['sourceExcerpt'] in source['text']
            description = next(r['text'] for r in right if r['id'] == mapping[item['id']])
            assert description in item['sourceExcerpt']


def test_ambiguity_conflicting_facts_and_acronym_aliases_are_rejected():
    data = chunks()[:1]
    data[0]['text'] += 'Round Robin is a scheduling algorithm that runs processes in their arrival order. '
    facts = q.reliable_facts(a.sentences(data))
    assert 'Round Robin' not in {fact['concept'] for fact in facts}
    assert generate(['mcq'], data=data)['questions'] == []
    data = [{'chunk_id':'c1','text':
        'First Come First Served is a scheduling algorithm that runs processes in their arrival order. '
        'FCFS is a scheduling algorithm that runs processes in their arrival order. '
        'Arrival Scheduling is a scheduling algorithm that runs processes in their arrival order.'}]
    assert generate(['matching', 'mcq'], data=data)['questions'] == []
    assert q.aliases('Round Robin', 'RR')


def test_fill_generator_reuses_source_exact_cloze_and_existing_quality_rules():
    data = [{'chunk_id':'c1', 'page':7, 'text':'Round Robin scheduling uses a fixed time quantum.'}]
    result = generate(['fill_blank'], data=data)['questions']
    assert len(result) == 1
    question = result[0]
    assert question['question'] == 'Complete the source sentence: Round Robin scheduling uses a fixed _____.'
    assert question['correctAnswer'] == 'time quantum' and question['pageStart'] == 7
    cards = a.generate('FLASHCARDS', data, 'Study', {})['cards']
    assert question['id'] == a.identifier('question', cards[0]['id'])
    assert question['sourceExcerpt'] == cards[0]['sourceExcerpt']


def test_cross_format_source_fact_and_concept_deduplication():
    result = generate(list(q.QUESTION_TYPES))['questions']
    facts = []
    for question in result:
        facts.extend(item['sourceExcerpt'] for item in question['leftItems']) if question['type'] == 'matching' else facts.append(question['sourceExcerpt'])
    assert len(facts) == len(set(facts))
    definitions = a.definitions(a.sentences(chunks()))
    concepts = [next(f['concept'] for f in definitions if f['text'] == source) for source in facts]
    assert len(concepts) == len(set(concepts))


@pytest.mark.parametrize('types,count', [([],12),(['invalid'],12),('mcq',12),(['mcq'],0),(['mcq'],31),(['mcq'],True)])
def test_options_validation(types, count):
    with pytest.raises(ValueError):
        q.quiz_options(types, count)


def test_count_limit_redistribution_and_quality_over_quantity():
    result = generate(['mcq','matching'], count=30, data=chunks()[:1])
    assert 0 < len(result['questions']) < 30 and result['messages']
    assert {item['type'] for item in result['questions']} <= {'mcq','matching'}
    assert len(generate(['mcq'], count=2)['questions']) == 2
    assert q.quiz_options() == {'questionTypes':['fill_blank','mcq'],'questionCount':12}


def test_generation_has_no_qwen_assistant_rag_or_model_calls(monkeypatch):
    forbidden = Mock(side_effect=AssertionError('Quiz called inference'))
    for name in ('rag.llm','rag.qa','assistant.qwen','assistant.orchestrator'):
        monkeypatch.setitem(sys.modules, name, SimpleNamespace(generate=forbidden, ask=forbidden, LuminaRLLM=forbidden))
    assert generate(list(q.QUESTION_TYPES))['questions']
    assert forbidden.call_count == 0
    tree = ast.parse((Path(__file__).parents[1]/'rag/services/knowledge_quiz.py').read_text(encoding='utf-8'))
    allowed = {'hashlib','itertools','random','re','rag.services.knowledge_algorithms','rag.services.knowledge_quiz_sources'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(item.name in allowed for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed


@pytest.mark.parametrize('selection', SELECTIONS)
def test_lecture_headings_colon_definitions_acronyms_and_list_families(selection):
    data = json.loads((FIXTURE.parent/'quiz_lecture_notes.json').read_text(encoding='utf-8'))
    result = generate(selection, data=data)
    assert {item['type'] for item in result['questions']} == set(selection)
    for question in result['questions']:
        entries = question['leftItems'] if question['type'] == 'matching' else [question]
        for item in entries:
            source = next(c for c in data if c['chunk_id'] == item['sourceChunkIds'][0])
            assert item['sourceExcerpt'] in source['text']
        if question['type'] == 'mcq':
            assert len(set(question['options'])) == 4
            assert 'Dynamic Programming (DP)' not in question['options']
            assert all(q.aliases(a, b) is False for a, b in combinations(question['options'], 2))
    assert result == generate(list(reversed(selection)), data=data)


def test_lecture_subjects_do_not_include_code_or_sentence_fragments():
    from rag.services.knowledge_quiz_sources import note_facts
    data = [{'chunk_id':'bad','text':
        'However, when a lot of recursive calls are required, memoization may cause memory problems.\n'
        'Let V is an array of the solution of sub-problems.\n'
        'Your goal is to reach the top with minimum total cost.\n'
        'lrs[i] is equal to lrs[j] and i is not equal to j.\n'
        'Commodities are manufactured on the same set of machines.'}]
    assert q.reliable_facts(a.sentences(data), note_facts(data)) == []
    assert generate(['mcq','matching'], data=data)['questions'] == []


def test_related_parent_term_does_not_delete_specific_application_fact():
    from rag.services.knowledge_quiz_sources import note_facts
    data = json.loads((FIXTURE.parent/'quiz_lecture_notes.json').read_text(encoding='utf-8'))
    data[1]['text'] += '\nMatrix multiplication is an associative operation that preserves the product under different parenthesizations.'
    facts = q.reliable_facts(a.sentences(data), note_facts(data))
    assert 'Matrix Chain Multiplication' in {f['concept'] for f in facts}


def test_lecture_parser_has_no_model_or_assistant_dependency():
    path = Path(__file__).parents[1]/'rag/services/knowledge_quiz_sources.py'
    allowed = {'re','collections','rag.services.knowledge_algorithms'}
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            assert all(item.name in allowed for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed
