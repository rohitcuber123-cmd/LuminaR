import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pymupdf as fitz
import pytest

from rag.services import private_document_ocr as o, document_knowledge as dk, knowledge_quiz_evidence as e, knowledge_quiz_formats as f


def pdf(tmp_path, kinds):
    path=tmp_path/'fixture.pdf';doc=fitz.open()
    for kind in kinds:
        page=doc.new_page()
        if kind=='scan':
            page.draw_rect(fitz.Rect(20,20,40,40),fill=(0,0,0))
    doc.save(path);doc.close()
    return path


TEXT='TCP is a transport protocol that delivers reliable ordered data between network applications.'


@pytest.mark.parametrize('text,valid',[(TEXT,True),('',False),('1234 %%% 000 1234',False),('aaa \x00\x01\x02 '*20,False),('\ufffd'*100,False)])
def test_native_quality_uses_multiple_signals(text,valid):
    assert o.usable(text)==valid


def test_healthy_native_skips_ocr(tmp_path):
    reader=Mock(side_effect=AssertionError('Native page entered OCR'))
    pages,stats=o.prepare(pdf(tmp_path,['text']),[{'page':1,'text':TEXT}],reader)
    assert pages[0]['text']==TEXT and stats['ocr_attempts']==0


def test_mixed_pages_selective_and_preserve_identity(tmp_path):
    reader=Mock(return_value=(TEXT,100))
    pages,stats=o.prepare(pdf(tmp_path,['text','scan','text']),[{'page':i+1,'text':TEXT if i!=1 else ''} for i in range(3)],reader)
    assert reader.call_count==1
    assert [r['extraction_method'] for r in pages]==['NATIVE','OCR','NATIVE']
    assert [r['page'] for r in pages]==[1,2,3] and stats['ocr_pages']==1


def test_blank_pages_no_ocr(tmp_path):
    reader=Mock(side_effect=AssertionError('Blank page entered OCR'))
    rows,stats=o.prepare(pdf(tmp_path,['blank']),[{'page':1,'text':''}],reader)
    assert stats['blank_pages']==1 and not rows[0]['text']


def test_page_failure_does_not_drop_native_following_page(tmp_path):
    rows,stats=o.prepare(pdf(tmp_path,['scan','text']),[{'page':1,'text':''},{'page':2,'text':TEXT}],Mock(side_effect=RuntimeError('engine')))
    assert stats['failed_pages']==1 and rows[1]['text']==TEXT and rows[0]['text']==''


def test_unusable_ocr_rejected(tmp_path):
    rows,stats=o.prepare(pdf(tmp_path,['scan']),[{'page':1,'text':''}],Mock(return_value=('12345 %%%',100)))
    assert stats['failed_pages']==1 and not rows[0]['text']


def test_ocr_page_limit_is_bounded(tmp_path):
    reader=Mock(return_value=(TEXT,100))
    rows,stats=o.prepare(pdf(tmp_path,['scan','scan']),[{'page':1,'text':''},{'page':2,'text':''}],reader,o.OCRConfig(page_limit=1))
    assert reader.call_count==1 and stats['failed_pages']==1 and rows[0]['extraction_method']=='OCR'


def test_oversized_page_rejected_before_raster_allocation(monkeypatch):
    monkeypatch.setattr(o,'capability',lambda:{'available':True})
    page=SimpleNamespace(rect=SimpleNamespace(width=100000,height=100000),get_pixmap=Mock(side_effect=AssertionError('Unbounded raster')))
    with pytest.raises(RuntimeError,match='OCR_PAGE_TOO_LARGE'):o.read_page(page)
    assert not page.get_pixmap.called


def test_missing_language_clean_capability(monkeypatch):
    monkeypatch.delenv('LUMINAR_TESSERACT',raising=False);monkeypatch.delenv('TESSDATA_PREFIX',raising=False)
    monkeypatch.setattr(o.shutil,'which',lambda _:None);monkeypatch.setattr(Path,'is_file',lambda _:False)
    assert not o.capability()['available']


def fact(label,desc,page=1,family='DEFINITION'):
    return {'id':label,'concept':label,'conceptKey':label.lower(),'description':desc,'sourceExcerpt':f'{label} is {desc}',
        'family':family,'category':None,'evidenceUnitIds':[label],'sourceChunkIds':['c'+str(page)],'pageStart':page,'fact':label,'score':1}


def test_cross_page_definition_distractors_are_all_sourced():
    facts=[fact('Router','a device forwarding packets between networks.',1),fact('Switch','a device forwarding local frames by hardware address.',2),
           fact('Bridge','a device filtering traffic between segments.',3),fact('Hub','a device repeating received signals to all ports.',4)]
    questions=f.mcqs(facts,{k:0 for k in e.REASONS})
    assert len(questions)==4
    assert all(len(q['options'])==4 and set(q['optionSources'])==set(q['options']) for q in questions)
    assert len(f.matching(facts,{k:0 for k in e.REASONS})[0]['sourceChunkIds'])>=3


def test_matching_requires_at_least_three_compatible_pairs():
    facts=[fact('Router','a device forwarding packets.'),fact('Switch','a device switching frames.')]
    assert not f.matching(facts,{k:0 for k in e.REASONS})


def test_different_relation_families_cannot_supply_options():
    facts=[fact('Router','a packet forwarding device.')]+[fact('Subject'+str(i),'a feature value '+str(i),family='PROPERTY') for i in range(3)]
    assert not f.mcqs(facts,{k:0 for k in e.REASONS})


def test_semantic_peers_rejected_even_with_low_lexical_overlap():
    left=fact('Node','a routing element.');right=fact('Host','a forwarding participant.')
    left['semanticPeers']=['Host']
    assert not e.compatible(left,right)


def test_synonym_alias_and_similar_right_sides_rejected():
    assert not e.compatible(fact('TCP','a protocol that delivers reliable data.'),fact('TCP protocol','a reliable transfer mechanism.'))
    assert not e.compatible(fact('Alpha','a protocol delivering reliable ordered frames.'),fact('Beta','a protocol delivering reliable ordered frames.'))


def test_structured_definition_keeps_exact_source_and_fragment_guard():
    chunks=[{'chunk_id':'c1','page':1,'text':'Transport\nTCP: a transport protocol that provides reliable delivery between communicating applications\nPiggybacking is the technique of delaying outgoing acknowledgment temporarily and'}]
    model=dk.build(chunks);e.attach(model)
    assert any(x['concept']=='TCP' and ':' in x['sourceExcerpt'] for x in model.quiz_evidence)
    assert not any(x['concept']=='Piggybacking' for x in model.quiz_evidence)


def test_heading_bullet_retains_two_evidence_units():
    model=dk.build([{'chunk_id':'c1','page':2,'text':'Reliable transport\n- The sender can transmit data before receiving an acknowledgement'}]);e.attach(model)
    assert any(len(x['evidenceUnitIds'])==2 for x in model.quiz_evidence)


def test_quiz_facet_attaches_once_without_changing_core():
    model=dk.build([{'chunk_id':'c1','page':1,'text':TEXT}]);before=json.dumps(model.concepts)
    e.attach(model);e.attach(model,Mock(side_effect=AssertionError('Repeated encoder')))
    assert json.dumps(model.concepts)==before and model.quiz_evidence_version==e.VERSION


def test_malformed_semantic_encoder_rejected_on_legacy_migration():
    model=dk.build([{'chunk_id':'c1','page':1,'text':TEXT+' UDP is a transport protocol that sends datagrams without establishing connections.'}]);model.quiz_semantic_prepared=False
    with pytest.raises(ValueError):e.attach(model,lambda texts:[[float('nan')]]*len(texts))


def test_later_good_frames_survive_early_distractor_starvation():
    bad=[fact('Isolated'+str(i),'unique unsupported option '+str(i),family='UNIQUE'+str(i)) for i in range(60)]
    good=[fact('Alpha','a first independent network definition.'),fact('Beta','a second packet switching service description.'),
          fact('Gamma','an isolated link transmission characteristic.'),fact('Delta','a separate transport routing mechanism.')]
    rejected={k:0 for k in e.REASONS};result=f.mcqs(bad+good,rejected)
    assert len(result)==4 and rejected['NO_COMPATIBLE_DISTRACTORS']==60


def test_candidate_search_is_bounded():
    facts=[fact('Subject'+str(i),'a unique description for item '+str(i),family='UNIQUE'+str(i)) for i in range(150)]
    rejected={k:0 for k in e.REASONS};assert not f.mcqs(facts,rejected)
    assert rejected['NO_COMPATIBLE_DISTRACTORS']==100


def test_structured_bullet_is_not_promoted_when_answer_is_incomplete():
    model=dk.build([{'chunk_id':'c1','page':1,'text':'Network features\n- Piggybacking is the technique of delaying outgoing acknowledgment temporarily and'}]);e.attach(model)
    assert model.quiz_rejections['SOURCE_FRAGMENT'] and not any(x['concept']=='Piggybacking' for x in model.quiz_evidence)


def test_three_pair_matching_with_fourth_ambiguous_alternative():
    facts=[fact('Alpha','a transport protocol that delivers reliable ordered information.'),fact('Beta','a link mechanism that broadcasts received signals.'),
           fact('Gamma','a routing element forwarding packets between networks.'),fact('Delta','a transport protocol that delivers reliable ordered information.')]
    questions=f.matching(facts,{k:0 for k in e.REASONS})
    assert questions and all(len(q['leftItems'])==3 for q in questions)


def test_exact_option_sources_do_not_include_invented_text():
    data=json.loads((Path(__file__).parent/'fixtures/quiz_lecture_notes.json').read_text())
    from rag.services.knowledge_quiz import generate_from_knowledge
    result=generate_from_knowledge(dk.build(data),{'questionTypes':['mcq'],'questionCount':12})
    for q in result['questions']:
        for source in q['optionSources'].values():
            assert any(source['sourceExcerpt'] in c['text'] for c in data)
