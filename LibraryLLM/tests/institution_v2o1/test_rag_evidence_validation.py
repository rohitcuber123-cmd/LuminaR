import pytest
from rag.query_types import grounded_book_overview,ordinary_book_intent


@pytest.mark.parametrize('question',['What are the major themes of this book?','What are the main themes of this book?','What are its themes?'])
def test_theme_grammar_remains_factual_but_requires_evidence_validation(question):
    passages=[{'work_id':'OL123W','title':'Indexed fixture','chunk_id':f'c{i}','text':'A generic passage with no established themes. '*8} for i in range(3)]
    assert ordinary_book_intent(question)['intent']=='FACTUAL'
    assert not grounded_book_overview(question,passages,'OL123W')


def test_theme_question_reaches_existing_validator_in_actual_qa(monkeypatch):
    from tests.test_urgent_document_rag import fake_engine,candidate
    passages=[dict(candidate(str(i),'A generic passage with no established themes. '*8,1),work_id='OL123W',title='Indexed fixture') for i in range(3)]
    engine,validations,_=fake_engine(monkeypatch,passages,verdict='NOT_SUPPORTED')
    result=engine.ask('What are the major themes of this book?',work_id='OL123W')
    assert len(validations)==1
    assert result['verdict']=='NOT_SUPPORTED'
