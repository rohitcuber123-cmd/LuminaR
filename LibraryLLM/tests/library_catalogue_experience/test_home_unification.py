from test_catalogue import catalogue, call, home


def recommend(client, library, candidates=(), limit=10, user=2):
    return call(client, user, 'POST', library['base'] + '/catalogue/recommendations',
                {'work_ids': list(candidates), 'limit': limit})


def test_local_recommendation_intersection(client, catalogue):
    a, _, ids = catalogue
    result = recommend(client, a, ['OL999W', 'OL1W', 'OL1W'], 3)
    assert result['intersection_count'] == 1
    assert result['results'][0]['library_book_id'] == ids[0]
    assert len(result['results']) == 3
    assert all(book['owned_by_current_library'] and book['library_id'] == a['id'] for book in result['results'])


def test_local_recommendation_fallback_local_only(client, catalogue):
    a, _, ids = catalogue
    result = recommend(client, a, ['OL999W'], 50)
    assert result['intersection_count'] == 0
    assert len(result['results']) == len(ids) == 10
    assert {b['library_book_id'] for b in result['results']} == set(ids)
    assert all(b['source'] == 'LIBRARY' for b in result['results'])


def test_local_only_book_recommendable(client, catalogue):
    a, _, ids = catalogue
    result = recommend(client, a, [], 50)
    assert {b['library_book_id'] for b in result['results'] if b['global_work_id'] is None} == set(ids[1:])


def test_empty_recommendations_explicitly_require_global_fallback(client, catalogue):
    _, b, _ = catalogue
    result = recommend(client, b, ['OL1W'])
    assert result['source']['catalogue_source'] == 'GLOBAL_FALLBACK'
    assert result['results'] == []


def test_recommendations_cannot_use_staff_authority(client, catalogue):
    a, _, _ = catalogue
    call(client, 1, 'POST', a['base'] + '/catalogue/recommendations', {'work_ids': ['OL1W']}, 403)


def test_recommendation_inputs_are_bounded(client, catalogue):
    a, _, _ = catalogue
    call(client, 2, 'POST', a['base'] + '/catalogue/recommendations', {'work_ids': ['OL1W'] * 201}, 422)
    call(client, 2, 'POST', a['base'] + '/catalogue/recommendations', {'limit': 51}, 422)


def test_home_category_preview_books_are_owned(client, catalogue):
    a, _, ids = catalogue
    payload = home(client, a)
    assert payload['subjects']
    for subject in payload['subjects']:
        book = subject['preview_book']
        assert isinstance(book['subjects'], list)
        assert book['library_book_id'] in ids and book['library_id'] == a['id']
        assert subject['subject'] in book['subjects']


def test_local_recommendations_do_not_merge_another_tenant(client, catalogue):
    a, b, _ = catalogue
    call(client, 1, 'POST', b['base'] + '/inventory/books',
         {'title': 'Other tenant only', 'subjects': ['Private'], 'copies': 1, 'idempotency_key': b['id']}, 201)
    result = recommend(client, a, ['OL1W'], 50)
    assert all(book['library_id'] == a['id'] and book['title'] != 'Other tenant only' for book in result['results'])
