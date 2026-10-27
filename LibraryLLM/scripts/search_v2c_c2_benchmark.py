"""Versioned corpus sanitation. Never imports or executes a parser/evaluator.

Only development content may be printed. Other partitions are handled as sealed
data for identity, provenance, and structural contamination audits.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import itertools

R = Path('reports')
VERSION = 'V2C-C-Benchmark-v2'


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def write(name, value):
    (R / ('search_v2c_c2_' + name)).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf8')


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def mode(value):
    return {'SEMANTIC': 'SMART', 'GENRE': 'GENRE_SUBJECT'}.get(value.upper(), value.upper())


def identity(row, scopes):
    return (normalized(row['query_text']), mode(row['search_mode']), row['scope_type'], row['workspace_type'],
            json.dumps(scopes.get(row['scope_type'], {'capabilities': {'access':'DENIED'}})['capabilities'], sort_keys=True),
            row.get('expected_action') or (row['family_id'] if row.get('requires_native_execution') else 'PARSER'))


def structure(row):
    """Conservative operation topology, independent of expected plans and outputs.

    Merge even lexically different families when they share operation presence.
    Native actions have distinct state transition graphs.
    Literal modes are grouped together by mode. Scope is deliberately omitted:
    it must not allow an exposed grammar into the final holdout.
    """
    if row.get('requires_native_execution'):
        return 'NATIVE:' + (row.get('expected_action') or row['family_id'])
    m = mode(row['search_mode'])
    if m != 'SMART':
        return 'LITERAL:' + m
    q = normalized(row['query_text'])
    features = []
    for key, pattern in [
        ('rating', r'\brat(?:ing|ings|ed)\b|\bstars?\b|\d\+'),
        ('year', r'\b(?:publish\w*|release\w*|year|after|before|onward)\b'),
        ('author', r'\bby\b'), ('title', r'\btitled\b'),
        ('negative', r'\b(?:not|exclud\w*|without|except)\b'),
        ('include', r'\b(?:include|included|subject|category)\b'),
        ('format', r'\b(?:online|digital\w*|physical\w*|hardcover|binding)\b'),
        ('availability', r'\b(?:available|request|loan|borrow)\b'),
        ('metadata', r'\b(?:pages?|edition|language|french|dollars|costing|difficulty|audience)\b'),
        ('preference', r'\b(?:beginner\w*|introduct\w*|advanced|research|reference|short\w*)\b'),
        ('sort', r'\b(?:sort|highest|newest|oldest)\b')]:
        if re.search(pattern, q):
            features.append(key)
    # Quoted and unquoted topic-only queries are conservatively one topology.
    return 'SMART:' + ','.join(features)


def main():
    scopes = json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
    rows = sum((read_rows(R/f'search_v2c_c_resume_{s}.jsonl') for s in ['development', 'calibration', 'heldout']), [])
    groups = defaultdict(list)
    for row in rows:
        groups[identity(row, scopes)].append(row)
    clean = []
    duplicates = []
    for key, group in groups.items():
        retained = group[0]  # Stored order, never parser output or label agreement.
        clean.append(deepcopy(retained))
        if len(group) > 1:
            duplicates.append({'old_row_ids': [r['query_id'] for r in group], 'canonical_identity': key,
                               'reason': 'Mode aliases resolve to the same mode and context',
                               'retained': retained['query_id'], 'discarded': [r['query_id'] for r in group[1:]]})
    # Family graph union: every family and every matching operation topology
    # stays in one partition, including contextual and structural equivalents.
    parent = {r['family_id']: r['family_id'] for r in clean}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        parent[find(b)] = find(a)
    topologies = defaultdict(set)
    for row in clean:
        topologies[structure(row)].add(row['family_id'])
    for families in topologies.values():
        first = min(families)
        for family in sorted(families):
            union(first, family)
    components = defaultdict(list)
    for row in clean:
        components[find(row['family_id'])].append(row)
    assignments = []
    exposed = []
    for root, component in sorted(components.items()):
        old_splits = {r['split'] for r in component}
        legacy = [r for r in component if r['family_id'] == 'h11_exact_mode']
        # Original author uses h11 identifier with suffix; review provenance is
        # the authoritative pre-exposure marker when spelling differs.
        legacy = [r for r in component if r['family_id'].startswith('h11') or any(c.get('code') == 'pre_exposed_before_evaluation' for c in r.get('label_review_concerns', []))]
        split = 'development' if 'development' in old_splits else 'calibration' if 'calibration' in old_splits or legacy else 'heldout'
        group_id = 'structure-' + hashlib.sha256('|'.join(sorted({r['family_id'] for r in component})).encode()).hexdigest()[:16]
        assignments.append({'structural_family_id': group_id, 'original_families': sorted({r['family_id'] for r in component}),
                            'previous_splits': sorted(old_splits), 'split': split, 'cases': len(component),
                            'development_exposure': 'development' in old_splits})
        for row in component:
            row.update(benchmark_version=VERSION, old_query_id=row['query_id'], original_split=row['split'],
                       split=split, structural_family_id=group_id, search_mode=mode(row['search_mode']))
            if row in legacy:
                row['exposure_status'] = 'EXPOSED_LEGACY_HOLDOUT'
                exposed.append({'old_query_id': row['query_id'], 'new_partition': split, 'status': row['exposure_status']})
            elif row['original_split'] == 'heldout' and split != 'heldout':
                row['exposure_status'] = 'STRUCTURAL_EQUIVALENT_OF_EXPOSED_OR_CALIBRATION_FAMILY'
            row['query_id'] = 'v2:' + row['old_query_id']
    # Six substantive, manually authored grammar/order combinations. Labels
    # inherit a sealed development parent; operators and entities are unedited.
    # No separate output-blind review is available, so all remain UNREVIEWED.
    sources = [r for r in clean if r['original_split'] == 'development' and not r.get('parent_query_id') and
               r['family_id'] in ['d01_explicit_rating','d05_by_vs_about','d12_multi_reordering']]
    additions = []
    candidates = [
        ('Fiction about wizards; rating above 3', 'fiction about wizards above rating of 3', 'paraphrase_word_order'),
        ('rated above 4: History', 'history rated above 4', 'paraphrase_word_order'),
        ('about coral; rating greater than 4.2', 'rating greater than 4.2 on books about coral', 'paraphrase_word_order'),
        ('George Orwell books about dystopia', 'books by George Orwell about dystopia', 'paraphrase_word_order'),
        ('Fiction\tbooks : above rating of 3 , about wizards !?', 'fiction about wizards above rating of 3', 'noisy_malformed'),
        ('History\tbooks : above rating of 4 ??', 'history rated above 4', 'noisy_malformed')]
    # Use an explicitly matching author/topic parent when available, otherwise
    # another meaningful reordered comparator case without manufacturing gold.
    candidates[3] = ('poetry; rated at most 3.5', 'poetry rated at most 3.5', 'paraphrase_word_order')
    for i, (text, original, category) in enumerate(candidates):
        source = next(r for r in sources if normalized(r['query_text']) == normalized(original))
        row = deepcopy(source)
        row.update(query_id=f'v2:c2-authored-{i+1:03}', old_query_id=None, query=text, query_text=text,
                   parent_query_id=source['query_id'], category=category, review_status='UNREVIEWED',
                   authoring_source='C2 authored clause reordering; unchanged explicit operands/operators',
                   review_source='No isolated independent review; UNREVIEWED', reviewer_type=None,
                   transformation={'kind':'clause reordering / whitespace noise with explicit field retained'})
        assert not row.get('protected_spans')
        additions.append(row)
    clean += additions
    assert len({identity(r, scopes) for r in clean}) == len(clean)
    assert len(exposed) == 10
    # New final holdout consists only of legacy UNOBSERVED structural components
    # disjoint from all development/calibration graph components. No near-copy
    # replacement from the exposed h11 family is generated.
    # The conservative audit exhausts the legacy unseen parser families. Author
    # replacements with NEW operation combinations, not paraphrases of exposed
    # literals. These are intentionally unreviewed and never evaluated here.
    existing_structures = {structure(r) for r in clean}
    replacement_families = 0
    for combination in itertools.combinations(['title','author','include','negative','rating','sort','year'], 5):
        prototype = deepcopy(next(r for r in clean if r['family_id']=='d01_explicit_rating'))
        for index in range(10):
            row = deepcopy(prototype)
            for key in list(row):
                if key.startswith('expected_'):
                    if isinstance(row[key], list):row[key] = []
                    elif isinstance(row[key], bool):row[key] = False
                    else:row[key] = None
            for key in ['rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive']:row[key]=False
            title = f'The Observatory Ledger Volume {index+1}'
            author = f'Adrian Vale {index+1}'
            clauses = []
            if 'title' in combination:
                clauses.append(f'book titled "{title}"');row['expected_title']=title;row['expected_title_entity']=title
            if 'author' in combination:
                clauses.append(f'by {author}');row['expected_author']=author
            if 'include' in combination:
                clauses.append('include Fiction');row['expected_subjects']=['Fiction']
            if 'negative' in combination:
                clauses.append('exclude Romance');row['expected_excluded_subjects']=['Romance']
            if 'rating' in combination:
                clauses.append(f'rating at least {2+index/10:g}');row['expected_rating_min']=2+index/10
            if 'sort' in combination:
                clauses.append('sort by title');row['expected_sort']='TITLE'
            if 'year' in combination:
                clauses.append(f'published after {2000+index}');row['expected_year_min']=2000+index;row['year_min_exclusive']=True
            text='; '.join(clauses)
            row.update(query=text,query_text=text,search_mode='SMART',scope_type='PRIVATE_PATRON',workspace_type='PATRON',
                       family_id=f'c2_sealed_composition_{replacement_families:02}',query_id=f'v2:c2-sealed-{replacement_families:02}-{index:02}',
                       template_id=f'c2_sealed_composition_{replacement_families:02}_normative_composition',
                       structural_family_id=f'c2-new-structure-{replacement_families:02}',split='heldout' if replacement_families%2==0 else 'calibration',
                       original_split='NEW_UNOBSERVED',old_query_id=None,parent_query_id=None,category='canonical',
                       review_status='UNREVIEWED',review_source='Pending independent output-blind semantic review',reviewer_type=None,
                       authoring_source='C2 deterministic normative composition; no heldout parser or evaluation output exists',
                       protected_spans=[],label_review_concerns=[],expected_semantic_text='',expected_soft_preferences=[],
                       expected_decision='EXECUTABLE',execution_allowed=True,expected_execution_allowed=True,
                       expected_intent='FIND_AUTHOR' if 'author' in combination else 'FIND_EXACT' if 'title' in combination else 'BROWSE_CATEGORY')
            if 'title' in combination:
                start=text.index(title);row['protected_spans']=[{'start':start,'end':start+len(title),'text':title}]
            topology=structure(row)
            if topology in existing_structures:break
            clean.append(row)
        else:
            assignments.append({'structural_family_id':row['structural_family_id'],'original_families':[row['family_id']], 'previous_splits':[], 'split':row['split'],'cases':10,'development_exposure':False})
            existing_structures.add(topology);replacement_families+=1
            if replacement_families==10:break
    assert replacement_families==10
    assert len({identity(r,scopes) for r in clean})==len(clean)
    review_path=R/'search_v2c_c2_independent_review.json'
    if review_path.exists():
        approvals={r['query_id'] for r in json.loads(review_path.read_text())['cases']
                   if r['review_status']=='AI_REVIEWED' and r['independently_confident_full_label'] and not r['parser_output_visible']}
        for row in clean:
            if row['query_id'] in approvals:
                row.update(review_status='AI_REVIEWED',reviewer_type='independent_output_blind_AI',
                           review_source='Independent output-blind AI semantic review /root/blind_label_review; reports/search_v2c_c2_independent_review.json; no parser/evaluator source or outputs')
    metadata_path=R/'search_v2c_c2_review_metadata.json'
    if metadata_path.exists():
        metadata=json.loads(metadata_path.read_text())
        allowed={'review_status','review_source','reviewer_type','review_provenance','label_reviewed','label_review_concerns'}
        for row in clean:
            if row['query_id'] in metadata:
                assert set(metadata[row['query_id']])<=allowed
                row.update(metadata[row['query_id']])
    files = []
    for split in ['development','calibration','heldout']:
        path = R/f'search_v2c_c2_v2_{split}.jsonl'
        selected = [r for r in clean if r['split'] == split]
        path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in selected), encoding='utf8')
        files.append({'path': str(path), 'split': split, 'cases': len(selected), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    counts = dict(Counter(r['category'] for r in clean))
    manifest = {'benchmark_version': VERSION, 'unique_cases': len(clean), 'duplicate_contexts': 0,
                'query_families': len({r['family_id'] for r in clean}), 'structural_families': len(assignments),
                'splits': dict(Counter(r['split'] for r in clean)), 'files': files, 'category_counts': counts,
                'review_counts': dict(Counter(r['review_status'] for r in clean)),
                'normalization': 'NFKC + casefold + whitespace collapse; punctuation retained. Canonical mode, scope, workspace, full capability profile and native action/scenario included. Gold never used for identity or retained-row selection.',
                'family_policy': 'Union every family sharing operation topology. Move every component touching evaluated development into development; calibration contamination moves to calibration. Pre-exposed h11 excluded from final holdout. Conservative graph may overmerge.',
                'labels_changed': 0, 'heldout_evaluated': False, 'calibration_run': False,
                'sealed_label_review':'100 independently flagged ambiguous; unreviewed, labels unchanged; no output seen. Final holdout is structurally isolated but semantic readiness is PARTIAL.',
                'new_cases': [r['query_id'] for r in additions]}
    write('benchmark_v2_manifest.json', manifest)
    write('benchmark_v2_dedup.json', {'version': VERSION, 'stored_v1_rows': len(rows), 'discarded_rows': len(rows)-len(groups), 'duplicates': duplicates, 'v2_duplicates': 0})
    write('benchmark_v2_split.json', {'version': VERSION, 'assignments': assignments, 'counts': manifest['splits']})
    write('exposed_holdout.json', {'version': VERSION, 'rows': exposed, 'removed_from_final_holdout': True, 'replacement': 'Conservative legacy structural audit exhausted unseen parser families. 100 new cases in ten previously absent operation topologies authored, split 50 calibration/50 heldout. UNREVIEWED; no output inspected. No exposed h11 paraphrases reused. Holdout size is not a quota.'})
    write('family_overlap_audit.json', {'version': VERSION, 'cross_split_family_overlap': 0, 'cross_split_structural_overlap': 0, 'components': assignments, 'contextual_overlap_resolution': 'Exact contexts and shared operation topologies union whole original families before assignment.'})
    write('category_counts.json', {'version': VERSION, 'unique_cases': len(clean), 'counts': counts, 'minimums': {'paraphrase_word_order':2000,'noisy_malformed':1000,'contradiction_negative':750,'ambiguous_incomplete':750,'multi_constraint':1000,'entity_number_protection':500,'tenant_security_scope':500}, 'duplicates_counted': False})
    write('review_provenance.json', {'version': VERSION, 'counts': manifest['review_counts'], 'human_reviewed':0, 'new_cases':'UNREVIEWED; root has seen development outputs, no independent-review claim', 'inherited_review':'Original independent review provenance preserved verbatim; generated derivatives remain UNREVIEWED.'})
    write('holdout_manifest.json', {'version': VERSION, 'status':'FROZEN_FOR_FUTURE_EVALUATION_NOT_AUTHORIZED_BY_C2', 'corpus_files':files, 'family_assignments_sha256':hashlib.sha256((R/'search_v2c_c2_benchmark_v2_split.json').read_bytes()).hexdigest(), 'heldout_evaluations':0, 'calibration_runs':0, 'parser_freeze':'Pending completion of bounded development changes; later changes invalidate freeze', 'decision_policy':'Existing categorical deterministic policy only; calibration not started'})
    print(json.dumps({k:manifest[k] for k in ['unique_cases','duplicate_contexts','query_families','structural_families','splits','category_counts','review_counts']}))


if __name__ == '__main__':
    main()
