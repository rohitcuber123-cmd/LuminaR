"""Educational quality contracts, independent of downloaded models."""
import json
from pathlib import Path
import numpy as np
from rag.services import document_knowledge as d

FIXTURE = Path(__file__).parent / 'fixtures/knowledge_educational.json'

def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf8'))

def test_wrapped_hyphens_and_invisible_pdf_characters():
    assert d.normalized('flow\u200b con-\ntrol  mechanism') == 'flow control mechanism'

def test_adjacent_duplicate_phrases_and_meaningful_repetition():
    assert d.clean_label('Sliding Window Sliding Window') == 'Sliding Window'
    assert d.clean_label('Noiseless Channels Noiseless Channel') == 'Noiseless Channel'
    assert d.clean_label('Very very') == 'Very very'

def test_headers_page_numbers_and_preface_are_not_study_items():
    model = d.build(fixture())
    assert model.metrics['boilerplate_rejections'] > 0
    assert all('college' not in c['label'].lower() and 'preface' not in c['label'].lower() for c in model.concepts)

def test_grounded_explanation_is_required_and_fragments_do_not_dominate():
    model = d.build(fixture())
    assert model.concepts and all(c['explanation'] and c['evidenceUnitIds'] for c in model.concepts)
    assert not {'idea', 'difference', 'stations', 'procedure'} & {c['label'].lower() for c in model.concepts}

def test_named_defined_single_words_survive_genericity_penalty():
    model = d.build([{'chunk_id':'dns','page':1,'text':'DNS is a network protocol that resolves domain names into numerical addresses for clients.'}])
    assert [c['label'] for c in model.concepts] == ['DNS']

def test_multi_page_sources_preserve_actual_page_to_chunk_mapping():
    text = 'Flow control is a mechanism that limits the amount of data sent before receiving acknowledgment.'
    model = d.build([{'chunk_id':'a','page':2,'text':text},{'chunk_id':'b','page':7,'text':text}])
    assert model.concepts[0]['sources'] == [{'chunkId':'a','page':2},{'chunkId':'b','page':7}]

def test_adaptive_count_is_bounded_and_does_not_fill_with_noise():
    model = d.build(fixture())
    assert 8 <= len(model.concepts) <= 30
    assert d.build([{'chunk_id':'bad','page':1,'text':'idea\ndifference\nprocedure\n1234'}]).concepts == []

def test_embedding_pass_is_pruned_single_and_semantic_duplicates_suppressed():
    calls = []
    def encoder(texts):
        calls.append(texts)
        # Two differently named heading explanations describe one mechanism.
        return np.array([[1.,0.],[.999,.001],[0.,1.]], dtype='float32')[:len(texts)]
    chunks = [ {'chunk_id':str(i),'page':i+1,'text':text} for i,text in enumerate([
        'Sliding Window\nThe sender can transmit several frames before an acknowledgment arrives.',
        'Window Flow Control\nThe sender can transmit several frames before an acknowledgment arrives.',
        'Pure ALOHA\nA station can transmit whenever it has a frame ready for transmission.' ]) ]
    model = d.build(chunks, encoder)
    assert len(calls) == 1 and len(calls[0]) <= d.MAX_EMBEDDINGS
    assert len(model.concepts) == 2 and model.metrics['duplicate_rejections']

def test_distinct_related_identity_definitions_are_retained():
    def encoder(texts):
        return np.array([[1.,0.],[.999,.001]], dtype='float32')
    model = d.build([{'chunk_id':'a','page':1,'text':
        'Send window is a buffer that holds frames transmitted without acknowledgment. '
        'Receive window is a buffer that accepts sequence numbers for incoming frames.'}], encoder)
    assert len(model.concepts) == 2

def test_all_artifacts_use_only_shared_model_without_reextracting(monkeypatch):
    model = d.build(fixture())
    monkeypatch.setattr(d, 'source_units', lambda *args: (_ for _ in ()).throw(AssertionError('reparsed')))
    for kind in ('KEY_CONCEPTS','FLASHCARDS','EXTRACTIVE_SUMMARY','MIND_MAP','QUIZ'):
        assert d.generate(kind, model, 'Educational notes', {'questionTypes':['mcq','matching'],'questionCount':12})

def test_cards_are_distinct_supported_knowledge_items():
    model = d.build(fixture())
    cards = d.generate('FLASHCARDS',model,'Study',{})['cards']
    assert len(cards) >= 10
    assert len({c['knowledgeItemId'] for c in cards}) == len(cards)
    assert all(c['knowledgeItemId'] in {f['id'] for f in model.facts} and c['sourceChunkIds'] for c in cards)

def test_semantic_map_edges_have_source_unit_evidence():
    model = d.build(fixture())
    assert model.relations
    units = {u['id'] for u in model.source_units}
    assert all(set(r['evidenceUnitIds']) <= units and r['evidenceUnitIds'] for r in model.relations)
    graph = d.generate('MIND_MAP',model,'Study',{})
    assert all(e['sourceChunkIds'] for e in graph['edges']) and len(graph['nodes']) <= 60

def test_composition_relation_points_from_whole_to_components():
    model=d.build([{'chunk_id':'a','page':1,'text':
        'Protocol Stack\nProtocol stack consists of application layers and transport layers for network communication.'}])
    relations=[r for r in model.relations if r['type']=='CONTAINS']
    assert relations and 'application layers' in relations[0]['targetText']

def test_summary_uses_distinct_sections_and_source_facts():
    model = d.build(fixture())
    summary = d.generate('EXTRACTIVE_SUMMARY',model,'Study',{'mode':'detailed'})
    assert len(summary['sections']) >= 3
    assert len({s['title'] for s in summary['sections']}) == len(summary['sections'])
    assert all(s['knowledgeItemId'] in {f['id'] for f in model.facts} for s in summary['sentences'])

def test_metrics_are_numeric_and_never_include_private_source_text():
    metrics = d.build(fixture()).metrics
    assert all(isinstance(value,(int,float,bool)) for value in metrics.values())

def test_wrapped_subject_aliases_do_not_create_duplicate_facts():
    model = d.build([{'chunk_id':'a','page':1,'text':
        'First Come\nFirst Served is a scheduling algorithm that runs processes in their arrival order.'}])
    assert [c['label'] for c in model.concepts] == ['First Come First Served']
    assert len(model.facts) == 1

def test_verified_distractor_families_survive_diversity_selection():
    model=d.build(fixture())
    quiz=d.generate('QUIZ',model,'Study',{'questionTypes':['mcq']})
    assert model.metrics['complete_fact_families'] >= 2
    assert len(quiz['questions']) >= 10

def test_rhetorical_questions_and_list_descriptions_are_not_process_steps():
    model=d.build([{'chunk_id':'p','page':1,'text':
        'Send Window\nSend window is a buffer that holds frames transmitted without acknowledgment.\n'
        '1. The first region defines sequence numbers belonging to already acknowledged frames.\n'
        '2. What if an acknowledgment frame is also lost?\n'
        '3. The sender must retain transmitted frames until their receipt has been acknowledged.'}])
    assert all('What if' not in f['text'] for f in model.facts)
    steps=[r for r in model.relations if r['type']=='HAS_STEP']
    assert all('first region' not in r['targetText'].lower() for r in steps)

def test_definition_conflicts_and_answer_leaking_mcqs_fail_closed():
    chunks = json.loads((FIXTURE.parent/'quiz_study.json').read_text())[:1]
    chunks[0]['text'] += ' Round Robin is a scheduling algorithm that runs processes in their arrival order.'
    model = d.build(chunks)
    quiz = d.generate('QUIZ',model,'Study',{'questionTypes':['mcq']})
    assert not quiz['questions']
