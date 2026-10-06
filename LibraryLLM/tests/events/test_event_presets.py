"""V1.1 publication requirements, preserving V1 generic fields and lifecycle."""
import json
from pathlib import Path
import pytest
from test_events import isolated, http, create, unseen, NOW  # pytest sibling module/fixture
from backend.schemas.events import Category
from backend.services.event_publish_validation import EVENT_PUBLISH_REQUIREMENTS as rules, publish_errors


def attempt(fixture, fields):
    draft = create(fixture, **fields)
    assert draft.status_code == 201
    row = draft.json()
    response = http(fixture).post('/staff/events/' + row['event_id'] + '/publish')
    return row, response


@pytest.mark.parametrize('category', list(rules))
def test_all_categories_allow_incomplete_drafts(isolated, category):
    row = create(isolated, category=category).json()
    assert row['status'] == 'DRAFT' and row['published_at'] is None
    assert row['related_work_ids'] == [] and not row['description']


@pytest.mark.parametrize('category', ['NEW_ARRIVALS', 'READING_CLUB'])
def test_book_required_only_on_publication(isolated, category):
    row, response = attempt(isolated, {'category': category})
    assert response.status_code == 422 and 'at least one' in response.json()['detail']
    path = '/staff/events/' + row['event_id']
    assert http(isolated).patch(path, json={'related_work_ids': ['OL1W', 'OL2W']}).status_code == 200
    published = http(isolated).post(path + '/publish')
    assert published.status_code == 200 and published.json()['related_work_ids'] == ['OL1W', 'OL2W']


@pytest.mark.parametrize('category,complete', [
    ('BOOK_SALE', {'start_at': NOW.isoformat(), 'location': 'Sale hall'}),
    ('WORKSHOP', {'start_at': NOW.isoformat(), 'location': 'Workshop hall', 'description': 'Learn together'}),
    ('CLOSURE', {'start_at': NOW.isoformat(), 'end_at': NOW.isoformat(), 'description': 'Maintenance'}),
])
def test_each_required_field_enforced_by_direct_api(isolated, category, complete):
    for field in complete:
        fields = {**complete, field: None if field.endswith('_at') else '', 'category': category}
        # End without start is already rejected by the canonical base schema.
        if field == 'start_at' and fields.get('end_at'): fields['end_at'] = None
        row, response = attempt(isolated, fields)
        assert response.status_code == 422
        assert rules[category]['fields'][field] in response.json()['detail']
        assert isolated[0].events.find_one({'event_id': row['event_id']})['status'] == 'DRAFT'
    _, response = attempt(isolated, {'category': category, **complete})
    assert response.status_code == 200 and response.json()['related_work_ids'] == []


@pytest.mark.parametrize('category', ['AUTHOR_EVENT','COMMUNITY_EVENT','LIBRARY_PROGRAM','LIBRARY_NOTICE','EXHIBITION','OTHER'])
def test_optional_categories_keep_base_contract(isolated, category):
    _, response = attempt(isolated, {'category': category})
    assert response.status_code == 200


def test_published_category_correction_preserves_publication_and_seen_state(isolated):
    unseen(isolated)
    _, response = attempt(isolated, {'category':'WORKSHOP','start_at':NOW.isoformat(),'description':'Talk','location':'Hall','related_work_ids':['OL2W','OL1W']})
    row = response.json(); path = '/staff/events/' + row['event_id']
    before = unseen(isolated)
    updated = http(isolated, 2).patch(path, json={'category':'COMMUNITY_EVENT'}).json()
    assert updated['published_at'] == row['published_at'] and updated['status'] == 'PUBLISHED'
    for field in ['description','start_at','location','related_work_ids']:
        assert updated[field] == row[field]
    assert unseen(isolated)['event_ids'] == before['event_ids']
    http(isolated, 3).post('/events/mark-seen', json={'cursor':before['seen_cursor']})
    assert http(isolated).patch(path, json={'category':'LIBRARY_NOTICE'}).status_code == 200
    assert unseen(isolated)['count'] == 0


def test_published_edit_cannot_remove_required_fields_or_adopt_invalid_category(isolated):
    _, response = attempt(isolated, {'category':'NEW_ARRIVALS','related_work_ids':['OL1W']})
    path = '/staff/events/' + response.json()['event_id']
    assert http(isolated).patch(path, json={'related_work_ids':[]}).status_code == 422
    assert http(isolated).patch(path, json={'category':'CLOSURE'}).status_code == 422
    assert http(isolated).get(path).json()['category'] == 'NEW_ARRIVALS'


def test_legacy_v1_publication_can_be_corrected_without_backfill(isolated):
    row = create(isolated, category='WORKSHOP').json(); path = '/staff/events/' + row['event_id']
    isolated[0].events.update_one({'event_id':row['event_id']},{'$set':{'status':'PUBLISHED','published_at':NOW}})
    assert http(isolated).patch(path, json={'summary':'Corrected existing V1 notice'}).status_code == 200
    assert http(isolated).patch(path, json={'category':'CLOSURE'}).status_code == 422


def test_publish_requirements_shared_contract_and_canonical_category_keys():
    root = Path(__file__).resolve().parents[2]
    assert set(rules) == {c.value for c in Category}
    assert rules == json.loads((root/'backend/schemas/event_publish_requirements.json').read_text())
    assert "../../../backend/schemas/event_publish_requirements.json" in (root/'frontend/src/lib/eventPresets.ts').read_text()
    assert not publish_errors({'category':'OTHER','related_work_ids':[]})


def test_whitespace_does_not_satisfy_publication_contract():
    assert {e['field'] for e in publish_errors({'category':'WORKSHOP','location':'  ','description':'\n','related_work_ids':[]})} == {'start_at','location','description'}


def test_no_new_preset_schema_fields_allowed(isolated):
    for field in ['preset_type','template_id','presenter','speaker','price']:
        assert create(isolated, **{field:'Injected'}).status_code == 422
