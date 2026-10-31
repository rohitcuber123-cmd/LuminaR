"""Review exact grounding delta using real filter/selection and controlled model."""
import pytest
from rag.book_assets import valid_work_id
from rag.document_grounding import definition_category,select_definition_evidence


@pytest.mark.parametrize('value,expected',[('OL123W',True),('OL0W',True),('doc_'+'a'*32,False),('OL123W\n',False),('ol123w',False),('',False),(None,False)])
def test_work_id_discriminator_is_not_an_ownership_grant(value,expected):
    assert valid_work_id(value) is expected


@pytest.mark.parametrize('verdict',['SUPPORTED','NOT_SUPPORTED'])
def test_document_definition_passes_real_fast_filter_to_original_validator(monkeypatch,verdict):
    from tests.test_urgent_document_rag import fake_engine,candidate,FLOW_DEFINITION
    from rag.fast_filter import run_fast_filter
    own=candidate('own',FLOW_DEFINITION,1)
    foreign=candidate('foreign',FLOW_DEFINITION+' Secret foreign detail.',9,document_id='foreign-doc')
    engine,validations,generated=fake_engine(monkeypatch,[foreign,own],verdict=verdict)
    monkeypatch.setattr('rag.qa.run_fast_filter',run_fast_filter)
    result=engine.ask('what is flow control',document_id='selected-doc')
    assert len(validations)==1
    assert validations[0][2]['informational_category']=='document_definition'
    assert [c['chunk_id'] for c in validations[0][1]]==['own']
    assert 'Secret foreign detail' not in generated[-1]
    assert result['verdict']==verdict
    assert [s['chunk_id'] for s in result['sources']]==(['own'] if verdict=='SUPPORTED' else [])


def test_no_authorized_document_evidence_never_calls_generation(monkeypatch):
    from tests.test_urgent_document_rag import fake_engine,candidate,FLOW_DEFINITION
    engine,validations,generated=fake_engine(monkeypatch,[candidate('foreign',FLOW_DEFINITION,9,document_id='foreign-doc')])
    result=engine.ask('what is flow control',document_id='selected-doc')
    assert not validations and not generated
    assert result['sources']==[]


@pytest.mark.parametrize('question',['why does flow control cause failure','prove flow control never fails','define flow control and prove its safety'])
def test_claims_do_not_receive_definition_category(question):
    from tests.test_urgent_document_rag import candidate,FLOW_DEFINITION
    evidence=[candidate('own',FLOW_DEFINITION,1)]
    assert definition_category(question,evidence,'selected-doc') is None
    assert select_definition_evidence(question,evidence,'selected-doc',7)==evidence
