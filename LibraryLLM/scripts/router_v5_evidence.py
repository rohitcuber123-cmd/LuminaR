"""Strict decision scoring and experiment utilities, never production imports."""
import hashlib
import json
from pathlib import Path
from assistant.router_v5.contracts import BY_ID

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name,data):
    path=ROOT/'reports'/f'assistant_router_v5_{name}.json'
    path.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')

def grade(row,out):
    if out is None:
        return False,{'decision':False}
    c=BY_ID[row['contract_id']]
    actual=out.model_dump(mode='json')
    checks={'intent':actual['intent']==c.intent,'goal':actual['goal']==c.goal,
            'ids':actual['resolved_work_ids']==row['expected_ids'],
            'field':actual['comparison_fields']==([row['field']] if row.get('field') else []),
            'criterion':bool(actual['criterion'])==bool(row.get('criterion_present')),
            'confirmation':bool(actual['requires_confirmation'])==c.mutation,
            'literal_safety':all(t.casefold() in row['message'].casefold() for t in actual['mentioned_titles'])}
    if c.id=='COMPARE_PREFERENCE':
        checks['clarification']=bool(actual['clarification_needed'])==(not bool(row.get('criterion_present')))
    if c.id in {'CONTINUE_RESULTS','REFINE_RESULTS'}:
        checks['operation']=actual['context_operation']==('SHOW_MORE' if c.id=='CONTINUE_RESULTS' else 'REFINE_RESULTS')
        if c.id=='REFINE_RESULTS':
            checks['usable_filter']=any([out.filters.available_only,out.filters.author,out.filters.subject,
                                       out.filters.exclude_seed_authors,out.filters.sort_preference!='relevance'])
    if c.id=='CATALOGUE_TOPIC_SEARCH':
        checks['original_query']=out.query==row['message']
    if c.id=='MISSING_REFERENCE':
        checks['clarification']=out.clarification_needed
    return all(checks.values()),checks

def totals(rows):
    accepted=[r for r in rows if r['accepted']]
    critical=[r for r in rows if r.get('critical')]
    fallback=[r for r in rows if not r['accepted']]
    def pct(n,d):return 100*n/d if d else None
    return {'total':len(rows),'accepted':len(accepted),'accepted_correct':sum(r['pass'] for r in accepted),
            'accepted_precision_percent':pct(sum(r['pass'] for r in accepted),len(accepted)),
            'coverage_percent':pct(len(accepted),len(rows)),
            'hybrid_correct':sum(r['pass'] for r in rows),'hybrid_accuracy_percent':pct(sum(r['pass'] for r in rows),len(rows)),
            'critical_total':len(critical),'critical_correct':sum(r['pass'] for r in critical),
            'critical_accuracy_percent':pct(sum(r['pass'] for r in critical),len(critical)),
            'fallback_count':len(fallback),'fallback_rate_percent':pct(len(fallback),len(rows)),
            'fallback_accuracy_percent':pct(sum(r['pass'] for r in fallback),len(fallback)),
            'qwen_calls_per_100':pct(sum(r.get('qwen_calls',not r['accepted']) for r in rows),len(rows))}
