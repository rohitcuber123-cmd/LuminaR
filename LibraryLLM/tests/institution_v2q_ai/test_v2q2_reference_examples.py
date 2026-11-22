"""Prompt examples must not teach nonexistent contextual book positions."""
import pytest
from assistant.qwen import QwenGateway


@pytest.mark.parametrize('key', ['page_books','selected_books'])
def test_single_book_examples_clarify_nonexistent_ordinals_and_bind_current_book(key):
    wid='8f911a1c-1cb2-434a-bd13-b0a7959bec66'
    examples=QwenGateway._reference_examples({key:[{'work_id':wid}]})
    for text in ['Is the second one available?','Tell me about the second one.','Tell me about the third one.']:
        assert examples[text]['i']=='clarify'
        assert examples[text]['s']=='ambiguous'
        assert 'e' not in examples[text] and 'w' not in examples[text]
    assert examples['Is this book available?']['w']==[wid]
    assert examples['Is this book available?']['s']==('page' if key=='page_books' else 'selected')


def test_pair_does_not_demonstrate_a_third_book():
    examples=QwenGateway._reference_examples({'active_result_context':{'work_ids':['OL1W','OL2W']}})
    assert examples['Tell me about the second one.']['e']=='SECOND'
    assert examples['Tell me about the third one.']['i']=='clarify'


def test_three_book_context_retains_noncontiguous_comparison_and_overviews():
    examples=QwenGateway._reference_examples({'active_result_context':{'work_ids':['OL1W','OL2W','OL3W']}})
    assert examples['Compare the first and third.']['w']==['OL1W','OL3W']
    assert examples['Tell me about the third one.']['e']=='THIRD'
    assert examples['Tell me about the second one.']['i']=='details'


def test_populated_list_prompt_examples_preserve_previous_revision_exactly():
    import json
    from pathlib import Path
    snapshot=json.loads((Path(__file__).parent/'fixtures/v2q1d_three_book_examples.json').read_text())
    for row in snapshot['rows']:
        assert json.dumps(QwenGateway._reference_examples(row['context']))==row['serialized_examples']
