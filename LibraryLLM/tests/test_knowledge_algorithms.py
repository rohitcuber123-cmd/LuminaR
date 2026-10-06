import ast
from pathlib import Path

from rag.services import knowledge_algorithms as a

TEXT = ('Virtual memory is a memory-management technique that allows secondary storage to extend apparent main memory. '
        'Paging is a memory-management scheme that divides memory into fixed-size pages. '
        'Encryption refers to the process of converting readable information into encoded data. '
        'A retention policy is a documented rule for keeping business records for a specified period. '
        'Virtual memory allows applications to access more storage than the available physical memory. '
        'Encryption protects sensitive business records during transmission across public networks. '
        'This is an example of a generic statement that should never become a definition card.')


def chunks(text=TEXT):
    return [{'chunk_id': 'c1', 'page': 4, 'text': text}, {'chunk_id': 'c2', 'page': 5, 'text': text}]


def test_concepts_stopwords_dedup_provenance_and_limit():
    data = chunks()
    result = a.concepts(a.sentences(data), data, limit=3)
    assert len(result) == 3
    assert len({a.normalize(c['label']) for c in result}) == len(result)
    assert all(a.valid_phrase(c['label']) and c['sourceChunkIds'] and c['pageStart'] == 4 for c in result)
    assert 'virtual memory' in [c['label'].lower() for c in result]
    assert a.concepts(a.sentences(chunks('The and a. aaaaaa 1234.')), []) == []


def test_summary_exact_extraction_order_redundancy_length_and_sources():
    result = a.generate('EXTRACTIVE_SUMMARY', chunks(), 'Manual', {'mode': 'quick'})['sentences']
    assert 1 <= len(result) <= 5
    assert len({s['text'] for s in result}) == len(result)
    assert all(s['text'] in TEXT and s['sourceChunkIds'] == ['c1'] for s in result)
    assert [TEXT.index(s['text']) for s in result] == sorted(TEXT.index(s['text']) for s in result)
    detailed = a.generate('EXTRACTIVE_SUMMARY', chunks(), 'Manual', {'mode': 'detailed'})['sentences']
    assert len(result) <= len(detailed) <= 12


def test_definition_quality_and_duplicates():
    weak = 'It is a useful thing to understand in daily life. Memory is memory and some other memory. '
    cards = a.generate('FLASHCARDS', chunks(TEXT + weak), 'Manual', {})['cards']
    definitions = [c for c in cards if c['type'] == 'definition']
    assert len(definitions) == 4
    assert len({c['concept'].lower() for c in definitions}) == 4
    assert all(c['back'] in TEXT and c['sourceChunkIds'] == ['c1'] for c in definitions)
    assert any(c['concept'].lower() == 'retention policy' for c in definitions)


def test_cloze_exact_restoration_and_no_generic_masks():
    cards = a.generate('FLASHCARDS', chunks(), 'Manual', {})['cards']
    cloze = [c for c in cards if c['type'] == 'cloze']
    assert cloze
    for c in cloze:
        assert c['front'].count('_____') == 1
        assert c['front'].replace('_____', c['back']) == c['sourceExcerpt']
        assert c['sourceExcerpt'] in TEXT and a.valid_phrase(c['back'])


def test_ambiguous_cloze_templates_rejected():
    text = ('Encryption protects records during transmission across public networks. '
            'Compression protects records during transmission across public networks.')
    cards = a.flashcards(a.sentences(chunks(text)), [{'label': 'Encryption'}, {'label': 'Compression'}])['cards']
    assert cards == []


def test_explicit_fixed_phrase_cloze_from_short_document():
    text = 'Round Robin scheduling uses a fixed time quantum.'
    cards = a.generate('FLASHCARDS', chunks(text), 'Scheduling', {})['cards']
    assert len(cards) == 1
    assert cards[0]['front'] == 'Round Robin scheduling uses a fixed _____.'
    assert cards[0]['back'] == 'time quantum'


def test_map_limits_edges_and_hierarchy_without_embeddings():
    data = [dict(c, chapter='Memory', section='Allocation') for c in chunks()]
    graph = a.generate('MIND_MAP', data, 'Manual', {})
    ids = {n['id'] for n in graph['nodes']}
    assert len(ids) == len(graph['nodes']) <= 60
    assert len({(e['source'], e['target']) for e in graph['edges']}) == len(graph['edges'])
    assert all(e['source'] in ids and e['target'] in ids for e in graph['edges'])
    assert {'chapter', 'section', 'concept', 'document'} <= {n['type'] for n in graph['nodes']}
    flat = a.generate('MIND_MAP', chunks(), 'Manual', {})
    assert all(e['source'] == 'document' for e in flat['edges'])


def test_quiz_grounding_and_safe_fallback():
    questions = a.generate('QUIZ', chunks(), 'Manual', {})['questions']
    assert 0 < len(questions) <= 12
    for q in questions:
        assert q['sourceExcerpt'] in TEXT and q['sourceChunkIds']
        if q['type'] == 'fill_blank':
            assert q['correctAnswer'] in q['sourceExcerpt']
        else:
            assert q['type'] == 'true_false' and q['correctAnswer'] == 'True'


def test_empty_missing_structure_and_large_document():
    for kind in ('KEY_CONCEPTS', 'EXTRACTIVE_SUMMARY', 'FLASHCARDS', 'MIND_MAP', 'QUIZ'):
        output = a.generate(kind, [], 'Empty', {'mode': 'quick'})
        if kind == 'QUIZ':
            assert output['questions'] == [] and output['messages']
        else:
            assert not any(v for v in output.values() if isinstance(v, list))
    rows = a.sentences([{'chunk_id': 'old', 'text': TEXT}])
    assert rows and all(r['pageStart'] is None and r['chapter'] is None for r in rows)
    many = [{'chunk_id': str(i), 'text': TEXT} for i in range(1500)]
    assert len(a.generate('FLASHCARDS', many, 'Large', {})['cards']) <= 40


def test_generation_modules_have_only_allowed_dependencies():
    allowed = {'hashlib', 'math', 're', 'collections', 'json', 'time', 'uuid', 'fastapi', 'rag.services', 'typing', 'pydantic', 'backend.dependencies', 'rag.services.knowledge_quiz'}
    for name in ('knowledge_algorithms.py', 'knowledge_artifacts.py', 'knowledge_routes.py'):
        tree = ast.parse((Path(__file__).parents[1] / 'rag/services' / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name in allowed for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.module in allowed or node.module == 'rag.services.knowledge_artifacts'
