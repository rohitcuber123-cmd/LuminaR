"""Correct report prose from frozen measured configuration; retain original evidence."""
from pathlib import Path
import hashlib, json

R = Path('reports')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def save(p, value):
    with Path(p).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2)


def main():
    old = load(R/'search_proof8_freeze_manifest.json')
    assert all(sha(p) == h for p,h in old['files'].items())
    cfg = load(R/'search_proof8a3_configuration.json')
    assert cfg['worker_tree_memory_cap_bytes'] == int(4.75*1024**3)
    observed = load(R/'search_proof8_observed_only_analysis.json')
    result = load(R/'search_proof8a3_comparison_results.json')
    ids = set(observed['observed_ids'])
    annotations = [x for x in result['annotation_records'] if x['id'] in ids]
    mandatory = [x for x in annotations if x['mandatory_comparable']]
    coverage = dict(observed_outputs=len(ids),
                    contexts_with_agreed_annotation_units=len({x['id'] for x in annotations}),
                    agreed_annotation_units=len(annotations),
                    contexts_with_agreed_mandatory_units=len({x['id'] for x in mandatory}),
                    note='Query02 has no exact-span aligned author/reviewer units for dimension scoring; it is excluded, not treated as correct. Schema/source and pipeline metrics still cover both outputs.')
    corrections = dict(
        type='Reporting revision only; no model, parser, prompt, labels or scorer modification',
        original_manifest_sha256=sha(R/'search_proof8_freeze_manifest.json'),
        attempt3_actual_RAM_cap_bytes=cfg['worker_tree_memory_cap_bytes'],
        correction='Original report prose copied the5.75GiB maximum from attempt2. Attempt3 dynamically rounded down to4.75GiB. Its configuration and QA numeric cap were already correct.',
        annotation_coverage=coverage)
    save(R/'search_proof8_reporting_corrections_r1.json', corrections)
    qa = load(R/'search_proof8_final_qa.json')
    qa['REPORTING_REVISION'] = corrections
    qa['RAW_EXTRACTION_METRICS']['observed_annotation_coverage'] = coverage
    save(R/'search_proof8_final_qa_r1.json', qa)
    text = (R/'search_proof8_final_report.md').read_text(encoding='utf-8')
    text = text.replace('# Standalone V8 local learned-extractor experiment',
                        '# Standalone V8 local learned-extractor experiment\n\nReporting revision1. This corrects the original prose RAM cap and clarifies annotation denominators; all original evidence is preserved.')
    assert 'within the5.75GiB cap' in text
    text = text.replace('within the5.75GiB cap', 'within the actual4.75GiB cap')
    text = text.replace('(5.75GiB cap +2GiB reserve +0.5GiB margin)', '(4.75GiB cap +2GiB reserve +0.5GiB margin)')
    text = text.replace('4/4 across the two observed contexts.',
                        '4/4 in the one observed context with agreed mandatory source annotations. Query02 has no exactly aligned author/reviewer annotation units and is excluded from these raw dimension scores; it remains included in schema and pipeline metrics.')
    text = text.replace('one model with two queued callers', 'two callers sharing one model (one active, one queued)')
    text = text.replace('`search_proof8_final_qa.json`', '`search_proof8_final_qa_r1.json`')
    # Keep generated numerical values unchanged while repairing missing spaces in prose.
    import re
    text = re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', text)
    text = re.sub(r'(?<=\d)(?=[A-Za-z])', ' ', text)
    # Restore exact paths, identifiers, model and revision strings affected by the prose pass.
    original = (R/'search_proof8_final_report.md').read_text(encoding='utf-8')
    import itertools
    for token in itertools.chain(re.findall(r'`[^`]+`', original), [cfg['revision'], 'Qwen2.5-3B-Instruct']):
        spaced = re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', token)
        spaced = re.sub(r'(?<=\d)(?=[A-Za-z])', ' ', spaced)
        text = text.replace(spaced, token)
    text = text.replace('search_proof 8_final_qa_r 1.json', 'search_proof8_final_qa_r1.json')
    with (R/'search_proof8_final_report_r1.md').open('x', encoding='utf-8') as f:
        f.write(text)
    paths = list(R.glob('search_proof8*')) + list(Path('scripts').glob('search_proof8*.py')) + list(Path('scratch/search_proof8_local').glob('*.py'))
    files = {str(p):sha(p) for p in paths if p.is_file()}
    save(R/'search_proof8_closeout_manifest_r1.json', dict(files=files, source='Reporting revision only',
                                                        previous_runtime_freeze_sha256=sha(R/'search_proof8_freeze_manifest.json')))
    failures = [p for p,h in files.items() if sha(p) != h]
    assert not failures
    save(R/'search_proof8_closeout_verification_r1.json', dict(entries=len(files), verified=True, failures=failures,
        manifest_sha256=sha(R/'search_proof8_closeout_manifest_r1.json'),
        historical_preservation='reports/search_proof8_preservation.json',
        original_freeze_unchanged=True, QA_required_fields=22))
    print(json.dumps(dict(report='reports/search_proof8_final_report_r1.md', entries=len(files), verified=True,
                          actual_attempt3_RAM_cap_bytes=cfg['worker_tree_memory_cap_bytes'], annotation_coverage=coverage)))


if __name__ == '__main__':
    main()
