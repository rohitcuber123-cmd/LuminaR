"""V1.1 synthetic API acceptance, latency, and marker-scoped cleanup."""
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
import check_events_live as v1


def run():
    f = v1.seed()
    checks = {}
    perf = {'draft_create': [], 'draft_edit': [], 'first_publish': [], 'editor_load': []}
    get = lambda: v1.request(f, 'readerA', 'GET', '/events/unseen')[0]
    get()
    start = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=7)).isoformat()
    end = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=8)).isoformat()
    row, _ = v1.create(f)
    published, _ = v1.request(f, 'librarian', 'POST', '/staff/events/' + row['event_id'] + '/publish')
    assert len(v1.request(f, 'readerA', 'GET', '/events/' + row['event_id'])[0]['related_books']) == 3
    assert get()['count'] == 1
    checks['A_new_arrivals_three_real_books_one_signal'] = True
    row, _ = v1.create(f, related_work_ids=[])
    path = '/staff/events/' + row['event_id']
    blocked, _ = v1.request(f, 'librarian', 'POST', path + '/publish', expected=422)
    assert 'at least one' in blocked['detail']
    v1.request(f, 'librarian', 'PATCH', path, {'related_work_ids': [f['book_ids'][0]]})
    v1.request(f, 'librarian', 'POST', path + '/publish')
    checks['B_empty_draft_saved_empty_publication_blocked_one_book_succeeds'] = True
    row, _ = v1.create(f, category='BOOK_SALE', title=f['marker'] + ' offline book sale', related_work_ids=[], start_at=start, location='Test sale hall')
    sale, _ = v1.request(f, 'admin', 'POST', '/staff/events/' + row['event_id'] + '/publish')
    assert not any(field in sale for field in ['price', 'payment', 'cart', 'checkout'])
    checks['C_offline_book_sale_publishes_without_books_or_commerce_fields'] = True
    row, _ = v1.create(f, category='CLOSURE', related_work_ids=[], start_at=start)
    path = '/staff/events/' + row['event_id']
    blocked, _ = v1.request(f, 'librarian', 'POST', path + '/publish', expected=422)
    assert 'Reopening' in blocked['detail']
    v1.request(f, 'librarian', 'PATCH', path, {'end_at': end})
    v1.request(f, 'librarian', 'POST', path + '/publish')
    checks['D_closure_missing_end_blocked_complete_closure_published'] = True
    row, _ = v1.create(f, category='WORKSHOP', start_at=start, end_at=end, location='Test workshop hall')
    path = '/staff/events/' + row['event_id']
    v1.request(f, 'librarian', 'PATCH', path, {'category': 'LIBRARY_NOTICE'})
    restored, _ = v1.request(f, 'librarian', 'PATCH', path, {'category': 'WORKSHOP'})
    for field in ['description', 'start_at', 'end_at', 'location', 'related_work_ids']:
        assert restored[field] == row[field]
    checks['E_api_type_switch_retains_generic_fields_and_book_order'] = True
    published, _ = v1.request(f, 'librarian', 'POST', path + '/publish')
    before = get()
    v1.request(f, 'readerA', 'POST', '/events/mark-seen', {'cursor':before['seen_cursor']})
    corrected, _ = v1.request(f, 'librarian', 'PATCH', path, {'category': 'COMMUNITY_EVENT'})
    assert corrected['published_at'] == published['published_at'] and get()['count'] == 0
    checks['F_published_category_correction_preserves_first_publication_and_no_fresh_signal'] = True
    f['published_workshop_id'] = row['event_id']
    # Restore the category for explicit UI confirmation testing. No new signal.
    v1.request(f, 'librarian', 'PATCH', path, {'category':'WORKSHOP'})
    v1.FIXTURE.write_text(json.dumps(f), encoding='utf8')
    for _ in range(5):
        row, elapsed = v1.create(f, title=f['marker'] + ' latency draft')
        perf['draft_create'].append(elapsed)
        path = '/staff/events/' + row['event_id']
        _, elapsed = v1.request(f, 'librarian', 'GET', path); perf['editor_load'].append(elapsed)
        _, elapsed = v1.request(f, 'librarian', 'PATCH', path, {'summary':'Updated draft'}); perf['draft_edit'].append(elapsed)
        _, elapsed = v1.request(f, 'librarian', 'POST', path + '/publish'); perf['first_publish'].append(elapsed)
    baseline = json.loads((v1.REPORTS/'events_performance.json').read_text(encoding='utf8'))['timings']
    compare = {'draft_create':'create_event','draft_edit':'edit_event','first_publish':'publish_event','editor_load':'event_detail'}
    timings = {name: {'samples_ms': values, 'median_ms': round(statistics.median(values),2), 'max_ms': max(values),
                      'v1_median_ms': baseline[compare[name]]['median_ms'],
                      'preferred_ms': 250 if name=='editor_load' else 500,
                      'within_budget': max(values) < (250 if name=='editor_load' else 500)} for name, values in perf.items()}
    v1.save('events_v1_1_live.json', {'pass':True,'api_checks':checks,'timings':timings,
        'browser_checks':{},'synthetic_records_only':True,'cleanup_pending':True,
        'performance_method':'Five actual HTTP samples; all publish samples are first publications. V1 local baseline is contextual, not a controlled benchmark.'})
    print(json.dumps({'api_checks':len(checks),'timings':timings,'marker':f['marker']}))


def cleanup():
    f = json.loads(v1.FIXTURE.read_text(encoding='utf8'))
    ids = [a['user_id'] for a in f['accounts'].values()]
    events = v1.db.events.delete_many({'created_by_user_id':{'$in':ids},'title':{'$regex':'^'+f['marker']}})
    states = v1.db.event_user_state.delete_many({'user_id':{'$in':ids}})
    users = v1.users_collection.delete_many({'user_id':{'$in':ids},'events_test_marker':f['marker']})
    assert users.deleted_count == len(ids)
    assert not v1.db.events.count_documents({'created_by_user_id':{'$in':ids}})
    v1.FIXTURE.unlink()
    report = json.loads((v1.REPORTS/'events_v1_1_live.json').read_text(encoding='utf8'))
    report.update(cleanup_pending=False,cleanup={'pass':True,'events_removed':events.deleted_count,'states_removed':states.deleted_count,'users_removed':users.deleted_count})
    v1.save('events_v1_1_live.json',report)
    print('V1.1 disposable fixture removed; original records preserved.')


if __name__ == '__main__':
    cleanup() if len(sys.argv)>1 and sys.argv[1]=='cleanup' else run()
