"""Assemble the final V4 report from saved evidence without model execution."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / f'assistant_router_v4_{name}.json').read_text(encoding='utf8'))


def write(name, data):
    (REPORTS / f'assistant_router_v4_{name}.json').write_text(json.dumps(data, indent=2), encoding='utf8')


def pct(value):
    return f'{100 * value:.2f}%'


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |',
                      *['| ' + ' | '.join(str(x).replace('|', '/') for x in row) + ' |' for row in rows]])


def main():
    names = ['baseline', 'dataset', 'dataset_gap', 'generation_quality', 'leakage', 'training', 'internal_test',
             'calibration', 'frozen_116', 'frozen_121', 'concurrency', 'live', 'resources', 'regression',
             'http_client_audit', 'restored_smoke', 'final_integrity', 'candidate_seal']
    data = {n: read(n) for n in names}
    a, b = data['frozen_116'], data['frozen_121']
    manifest = json.loads((ROOT / 'assistant/models/router_v4/manifest.json').read_text(encoding='utf8'))
    reg = data['regression']
    suite = ET.parse(REPORTS / 'assistant_router_v4_final_unit.xml').getroot().find('testsuite')
    reg['backend_groups']['final_unit'] = {k: float(suite.attrib.get(k, 0)) for k in ['tests', 'failures', 'errors', 'skipped', 'time']}
    write('regression', reg)
    f1, f2 = a['selective'], b['selective']
    live, training, gap = data['live'], data['training'], data['dataset_gap']
    critical_correct = sum(d['metrics']['critical_context']['passed'] for d in [a, b])
    critical_total = sum(d['metrics']['critical_context']['total'] for d in [a, b])
    gates = [
        ['Accepted precision >=97%, both', f"{f1['accepted_precision_percent']:.2f}% / {f2['accepted_precision_percent']:.2f}%", False],
        ['Accepted coverage >=70%, both', f"{f1['coverage_percent']:.2f}% / {f2['coverage_percent']:.2f}%", False],
        ['Hybrid >=90% / >=85%', f"{a['metrics']['strict']['percent']:.2f}% / {b['metrics']['strict']['percent']:.2f}%", False],
        ['Critical context >=95%', pct(critical_correct / critical_total), False],
        ['Fallback <=30%, both', f"{f1['fallback_rate_percent']:.2f}% / {f2['fallback_rate_percent']:.2f}%", False],
        ['Live sports / second / account / Search', '5/6; 5/5; 3/4; 1/2', False],
        ['Page / previous comparison / selection change', '1/3; 0/2; 1/1', False],
        ['20 classifier routes p95 <1 second', '784.97 ms default; 686.27 ms experimental batching', True],
        ['Classifier independent of GPU lock; runtime CUDA delta zero', 'Zero lock acquisitions; zero bytes', True],
        ['Fuzzy-title and unrelated Search false positives zero', '0 / 0 on both frozen sets', True],
        ['Concurrent users resolve their own complete context', 'No observed crossover; 0/20 successful book responses', False],
        ['Preserve other algorithms and V3 evidence', 'Hash audit confirms authorized shared changes only', True],
        ['Production build', reg['build'], reg['build'] == 'PASS'],
    ]
    write('decision', {'status': 'FAIL', 'production_mode': 'existing_qwen', 'gates':
                      [{'requirement': r, 'observed': v, 'passed': passed} for r, v, passed in gates],
                      'shadow': 'SKIPPED: offline gates failed', 'frozen_evaluations_once_only': True,
                      'no_post_frozen_training_or_calibration': True})
    sections = []
    def add(letter, title, body):
        sections.append(f'## {letter}. {title}\n\n{body}\n')
    add('A', 'Final result: FAIL', 'V4 is evaluated and remains an experimental artifact. Both frozen precision gates failed, as did coverage, hybrid accuracy, critical context and required live cases. Production remains `existing_qwen`. No promotion, additional model, post-test fine-tuning or threshold reduction occurred.\n\n' +
        table(['Gate', 'Observed', 'Result'], [[r, v, 'PASS' if passed else 'FAIL'] for r, v, passed in gates]))
    add('B', 'V3 baseline', table(['Metric', '116', '121'], [
        ['Accepted correct / accepted', '25/27', '26/30'], ['Accepted precision', '92.59%', '86.67%'],
        ['Coverage', '23.28%', '24.79%'], ['Hybrid strict', '81/116 (69.83%)', '60/121 (49.59%)']]) +
        '\n\nV3 combined critical context: 58.10%; fallback approximately 75%. V3 sources, artifacts, calibration, datasets and saved evaluations were hashed before work; see `assistant_router_v4_baseline.json` and the final integrity report.')
    add('C', 'Training distribution gap', 'The evidence supports template bias, but does not establish causation. V3 repeated politeness wrappers and had one focused book in 80.04% of cases. V4 covers 14 authority states equally and several tray sizes, but **85.71% still contain one focused book**. That explicit distribution requirement was not fully achieved. Frozen language is shorter and contains more varied lexical combinations. V4 still underrepresents short elliptical turns and no-focus/full-pair states.\n\n' +
        table(['Corpus', 'Mean words', 'Unique messages', 'Skeletons', 'Vocabulary', 'Distinct bigram ratio'],
              [[n, f"{gap[n]['words_mean']:.2f}", gap[n]['unique_messages'], gap[n]['unique_skeletons'], gap[n]['vocabulary'], f"{gap[n]['distinct_bigram_ratio']:.3f}"] for n in ['v3', 'v4', 'frozen_116', 'frozen_121']]) +
        '\n\nThese are diagnostic comparisons, not frozen targets used for optimization. Full intent/reference/position/context and syntax-proxy distributions are in `assistant_router_v4_dataset_gap.json`. Frozen sets do not independently label every ordinal word; context/binding diagnostics are identified accordingly.')
    add('D', 'V4 dataset size', f"{data['dataset']['size']:,} total cases; {data['dataset']['unique_messages']:,} unique messages across 208 semantic seed families. TRAIN contains 9,590 cases, within the requested 8,000–20,000 training target. Counts include context permutations, not 15,162 independently authored utterances.")
    add('E', 'Data sources', 'Manually authored seeds, existing local Qwen2.5-3B offline paraphrases, deterministic context/field/criterion permutations, and generic character transpositions (8% of TRAIN). Labels originate from seeds. No private conversations, production logs, or frozen evaluation utterances entered training. Final origin counts: 7,392 manual-seed cases; 7,770 approved Qwen-origin cases after expansion.')
    add('F', 'Manual quality review', '364 generated strings passed initial format collection; automatic filtering retained 305. Rejections: format/entity 4, placeholder drift 21, duplicate 1, too distant 31, too close 2. Similarity band: 0.55–0.965. A stratified 202-item review found 45 wrong meanings/label drifts (22.28%), eight awkward strings and zero remaining duplicates. All 305 were manually compared by the coding agent with their seeds; 227 were retained after conservative item/family rejection, and three ambiguous seeds were repaired before training. This was agent review, **not independent human annotation**. The large initial error rate prompted the semantic accept-list; similarity filtering alone was inadequate.')
    clusters = gap.get('shared_embedding_cluster_audit', {})
    cluster_text = '\n\n' + table(['Group', 'Occupied /64', 'Entropy bits', 'Effective clusters', 'Largest cluster'],
        [[n, d['occupied_clusters'], f"{d['entropy_bits']:.3f}", f"{d['effective_clusters']:.1f}", pct(d['largest_cluster_fraction'])]
         for n, d in clusters.get('groups', {}).items()]) if clusters else '\n\nShared V3/frozen cluster audit unavailable; only the original V4 64-cluster diagnostic exists.'
    add('G', 'Template diversity', 'V4 has 462 delexicalized skeletons and 5.21 unique messages per seed family, versus V3’s 840 skeletons and 11.71 messages per template family. V4 vocabulary and bigram diversity increased, while context replication inflates case count (32.82 cases/skeleton). Thus a larger corpus did not establish greater semantic breadth. Skeleton normalization is a heuristic lower-bound diagnostic, never a production language rule. Shared message-embedding clusters use cached base MiniLM, unique messages, 64 clusters and seed 947; the post-evaluation audit changes no model or predictions.' + cluster_text)
    add('H', 'TRAIN / DEV / INTERNAL split', 'Seed families were assigned before generation: four of eight seeds per type to TRAIN (104 families), two to DEV (52), two to INTERNAL (52). All paraphrases/context variants remain within their family split. Final sizes: 9,590 / 3,724 / 1,848. Normalized messages also remain disjoint. Family separation reduces leakage but does not remove shared writing style or semantic-type/template bias.')
    leak = data['leakage']
    add('I', 'Leakage audit', f"Exact frozen-text overlap: {leak['exact_overlap']}; family split overlap: {leak['family_split_overlap']}; near-duplicate flags at 0.97: {len(leak['near_flags'])}. Maximum embedding similarity: {leak['max_similarity']:.4f}; p95: {leak['p95_similarity']:.4f}. Frozen text was inspected only for distribution/leak auditing; no frozen labels entered losses, calibration or candidate selection. Both sealed evaluations ran once, after the candidate/runtime seal. The exclusive started marker prevents a second invocation.")
    add('J', 'Encoder input', '```text\n[MSG] which one is available?\n[STATE] active=SELECTION focus=1 changed=False awaiting=False document=False book_access=False\n[SEL] 1|Public book title ; 2|Other public title\n[CMP] none\n[REC] none\n[PAGE] none\n[RECENT] none\n```\n\nThe encoder sees public titles, ordinal positions and structural authority. Titles are bounded to 64 characters; each pool to four books; input to 256 tokens. Current message precedes current state/selection and older context. Work IDs, document IDs and private/account facts are excluded/redacted. IDs stay in parent-side binding. No descriptions or authors are serialized. Twenty-four existing numerical context features join the 384-dimensional normalized embedding.')
    ablations = []
    for name, trial in training['ablations'].items():
        if name == 'V3_old_heads':
            continue
        ablations.append([name, pct(trial['dev']['coverage']), pct(trial['dev']['accepted_precision']),
                          pct(trial['internal']['coverage']), pct(trial['internal']['accepted_precision'])])
    point = training['final_operating_point']
    ablations.append(['Fine-tuned critical / independent', pct(point['dev']['coverage']), pct(point['dev']['accepted_precision']),
                      pct(point['internal']['coverage']), pct(point['internal']['accepted_precision'])])
    old = training['ablations']['V3_old_heads']['internal']
    add('K', 'Frozen vs fine-tuned encoder', table(['Variant', 'DEV coverage', 'DEV precision', 'INTERNAL coverage', 'INTERNAL precision'], ablations) +
        f"\n\nOld V3 heads on V4 INTERNAL: coverage {pct(old['coverage'])}, raw subtype accuracy {pct(old['subtype_accuracy'])}; no comparable accepted-semantic precision was recorded for that legacy audit. A=message only; B=message+numeric; C=serialized context; D=serialized+numeric. Context serialization improves conservative internal coverage over A, but does not deliver the required generalization. Frozen V4 ablations used calibrated balanced linear heads. Only the sealed fine-tuned candidate was run against frozen116/121.")
    trials = []
    for trial in training['fine_tune_trials']:
        for policy, val in trial['policies'].items():
            trials.append([trial['variant'], policy, pct(val['dev']['coverage']), pct(val['dev']['accepted_precision']),
                           pct(val['internal']['coverage']), pct(val['internal']['accepted_precision'])])
    add('L', 'Independent vs joined action', table(['Loss', 'Policy', 'DEV coverage', 'DEV precision', 'INTERNAL coverage', 'INTERNAL precision'], trials) +
        '\n\nSeven multitask heads share the encoder. The joint action head has 31 semantic actions, including FIELD:attribute subclasses; the independent policy combines family/subtype consistency with relevant field/reference/position/criterion heads. The final precision-first comparison selected critical/independent. Both variants failed the INTERNAL 97% precision gate. Loss-masked irrelevant heads were removed from admission checks before sealing; no class thresholds were lowered. Trial-local `selected_policy` fields describe earlier DEV-only choices; the final operating point and artifact manifest are authoritative.')
    add('M', 'Chosen architecture and training', 'Cached all-MiniLM-L6-v2, fine-tuned shared encoder, seven linear heads, two-thread CPU worker, bounded queue (64), one encoder per worker, default batch size one. Six-epoch maximum, DEV-loss early stopping (patience two), encoder LR 2e-5, head LR 0.002, AdamW decay 0.01, batch 32, gradient clipping 1.0, action-balanced sampling and relevant-head loss masks. Chosen epoch was the lowest DEV loss (epoch five). Loss weights: family 0.3, subtype 1, reference 1, position 1.2, field 0.8, criterion 0.6, action 1.2. Two loss variants were trained on each of two V4 corpus versions (four complete fine-tuning trials); the first corpus lacked some DEV field/criterion slots and was archived/repaired before frozen execution. Aborted plumbing/precompute attempts are preserved too.\n\nDEV temperature scaling, per-class confidence/margin thresholds, centroid OOD floor and structural consistency control admission. Empirical class precision target is 97%, minimum 12 DEV cases per class, margin 0.05; disabled classes have thresholds above one. OOD floor: ' + f"{data['calibration']['ood_min_similarity']:.6f}." + ' This is not a statistical population guarantee. Mutation requests retain Qwen plus confirmation. Free-form criteria and explicit entities retain extraction fallback. Qwen uses the existing resident model; maximum one routing call per rejected frozen request.')
    head_params = sum((manifest['input_dimension'] + 1) * len(labels) for labels in manifest['heads'].values())
    add('N', 'Model size', f"Base MiniLM encoder approximately 22.7 million parameters, 384-dimensional output; seven heads contain {head_params:,} parameters over 408 inputs. Final artifact totals {manifest['artifact_bytes']:,} bytes ({manifest['artifact_bytes']/1048576:.2f} MiB). Safe encoder serialization plus tensor-only head loading; every artifact file is hash-verified. Manifest seal: `{data['candidate_seal']['manifest_sha256']}`. Dataset/seed hashes, framework versions, loss weights, thresholds and encoder hashes are in the manifest.")
    add('O', 'CPU and host RAM', 'Worker startup 11.08 seconds, startup RSS 777 MiB; live startup RSS 768 MiB. Peak observed benchmark RSS 888 MiB. Some no-batch samples reported 429 MiB after Windows working-set trimming; this is not the model’s full memory budget. Two threads used approximately 189–197% CPU under load. Host RAM 15,677 MiB; live service/commit snapshots include Mongo, Core, Search, Recommendation, RAG and Vite. Search had substantial pre-existing commit usage (~14.2 GiB); RAG ~8.4 GiB process commit. Windows commit includes nonresident/address-space effects and cannot be summed as physical RSS. Search subprocess regression ran serially, and normal services were reused for live load. No V4 Windows paging/commit failure was observed. Final restored-service snapshot is in `assistant_router_v4_restored_smoke.json`; its available physical RAM was ~1.6 GiB, so resource headroom remains limited.')
    add('P', 'GPU usage', 'Training used CUDA offline. Runtime router worker reported `device=cpu`, `cuda_initialized=false`, allocated CUDA bytes zero. Both concurrency configurations changed CUDA allocation by zero bytes and never acquired the Qwen GPU lock. Existing RAG/Qwen CUDA allocation (~2.27 GB) is separate. A real held Qwen inference lock did not block 20 CPU classifier routes (p95 736.20 ms).')
    for letter, title, metric in [('Q', 'Intent accuracy', 'intent'), ('R', 'Reference accuracy', 'reference_handle'), ('S', 'Position accuracy', 'position')]:
        values = [d['metrics'][metric] for d in [a, b]]
        body = table(['Frozen set', 'Hybrid correct / applicable', 'Hybrid accuracy'],
                     [[n, f"{v['passed']}/{v['total']}", f"{v['percent']:.2f}%"] for n, v in zip([116, 121], values)])
        head = {'intent':'intent_subtypes', 'reference_handle':'reference', 'position':'position_binding'}[metric]
        body += '\n\nRaw V4 pre-admission component accuracy: ' + '; '.join(f"{n}: {d['selective']['components'][head]['correct']}/{d['selective']['components'][head]['total']} ({d['selective']['components'][head]['accuracy_percent']:.2f}%)" for n, d in [(116, a), (121, b)]) + '.'
        if metric == 'position':
            body += ' Position is canonical book-binding equivalence, not independently annotated ordinal labels; explicit named entities are excluded.'
        add(letter, title, body)
    relevant = {}
    for name, d in [('116', a), ('121', b)]:
        field_cases = [c for c in d['cases'] if c['fields']]
        criterion_cases = [c for c in d['cases'] if c['expected_goal'] == 'PREFERENCE_COMPARE']
        relevant[name] = {'field_total': len(field_cases), 'field_head_correct': sum(c['telemetry']['components']['fields']['label'] in c['fields'] for c in field_cases),
                          'field_hybrid_exact': sum(c['comparison_fields'] == c['fields'] for c in field_cases),
                          'criterion_total': len(criterion_cases), 'criterion_head_correct': sum((c['telemetry']['components']['criterion']['label'] == 'PRESENT') == bool(c['criterion']) for c in criterion_cases)}
    write('relevant_components', {'method': 'Descriptive recomputation from saved frozen predictions; no model calls or tuning. Excludes loss-masked field/criterion targets.', 'sets': relevant})
    add('T', 'Field accuracy', table(['Frozen set', 'Relevant field head correct', 'Hybrid exact requested fields'],
        [[n, f"{v['field_head_correct']}/{v['field_total']}", f"{v['field_hybrid_exact']}/{v['field_total']}"] for n, v in relevant.items()]) +
        '\n\nOnly explicitly requested field cases are meaningful for this loss-masked head. The legacy all-case `selective.components.fields` counters include irrelevant targets and should not be interpreted as field accuracy. Fine-tuned INTERNAL relevant-field accuracy is ' + pct(data['internal_test']['components']['fields']['accuracy']) + '.')
    add('U', 'Criterion-presence accuracy', table(['Frozen set', 'Raw relevant preference-head correct', 'Hybrid explicit criterion required'],
        [[n, f"{v['criterion_head_correct']}/{v['criterion_total']}", f"{d['metrics']['criterion_presence']['passed']}/{d['metrics']['criterion_presence']['total']} ({d['metrics']['criterion_presence']['percent']:.2f}%)"] for (n, v), d in zip(relevant.items(), [a, b])]) +
        '\n\nHybrid explicit-criterion accuracy includes existing interpretation fallback. Criterion detection does not extract free text; criterion-positive requests retain Qwen extraction. All-case raw criterion counters include masked/nonpreference cases and are descriptive only.')
    add('V', 'Accepted precision', f"116: 46/52 = {f1['accepted_precision_percent']:.2f}%; 121: 36/48 = {f2['accepted_precision_percent']:.2f}%. Both fail 97%. False accepts were not hidden by compatibility scoring. INTERNAL had 269/278 = 96.76%, already below the gate before frozen testing.")
    add('W', 'Accepted coverage', f"116: 52/116 = {f1['coverage_percent']:.2f}%; 121: 48/121 = {f2['coverage_percent']:.2f}%. Both fail 70%. Higher coverage than V3 came with lower precision. Risk/coverage curves are descriptive cached-prediction summaries; no post-test operating point was selected.")
    add('X', 'Qwen fallback rate', f"116: 64/116 = {f1['fallback_rate_percent']:.2f}%; 121: 73/121 = {f2['fallback_rate_percent']:.2f}%. Confidence gating, invalid/ambiguous references, explicit entity extraction and complex/free-form interpretation retain fallback. Both fail <=30%.")
    add('Y', 'Qwen calls per 100 requests', f"116: {f1['qwen_calls_per_100']:.2f}; 121: {f2['qwen_calls_per_100']:.2f}. Maximum one routing call, zero routing prose calls and zero retries on these runs. Accepted classifier routes use zero Qwen calls. These metrics are routing calls, not total generative RAG work.")
    add('Z', 'Hybrid frozen 116', '84/116 = **72.41%**, versus V3 69.83%; required 90%. This is strict output semantics including intent, authoritative references, fields/goal/criterion and clarification where applicable.')
    add('AA', 'Hybrid frozen 121', '68/121 = **56.20%**, versus V3 49.59%; required 85%. Compatibility-only accuracy is 69/121, but strict 68/121 is the decision metric.')
    add('AB', 'Critical contextual accuracy', f"116: 61/88 = 69.32%; 121: 47/91 = 51.65%; combined {critical_correct}/{critical_total} = {pct(critical_correct/critical_total)}. Required 95%. Held-out previous-comparison strict accuracy was 1/16; selection change 1/3; page 3/5. Frozen generalization remains poor.")
    add('AC', 'Safety false positives', 'Both frozen sets: contextual fuzzy-title false positives zero, unrelated contextual Search fallbacks zero, schema/semantic-invalid outputs zero. Mutations retain existing confirmation and authorization. No account credentials or private content were saved in live evidence. Zero crossover was observed in 20 concurrent users, but the functional isolation gate failed because none returned the requested complete book response; absence of output cannot prove useful context resolution.')
    chain_rows = [[c['name'], sum(t['pass'] for t in c['turns']), len(c['turns']), sum(t['qwen_calls'] or 0 for t in c['turns'])] for c in live['chains']]
    live_rows = []
    for chain in live['chains']:
        for turn in chain['turns']:
            confidence = turn.get('components', {}).get('intent_subtypes', {}).get('confidence')
            live_rows.append([chain['name'], turn['message'], 'PASS' if turn['pass'] else 'FAIL',
                              turn['classifier_accepted'], f'{confidence:.4f}' if confidence is not None else 'unavailable',
                              turn['qwen_calls'], f"{turn['latency_ms']:.1f}", ', '.join(turn['resolved_ids']) or 'none'])
    add('AD', 'Live conversational chains', table(['Chain', 'Correct', 'Required cases', 'Routing Qwen calls'], chain_rows) +
        '\n\nReal public catalogue pairs: Economics of Football / The Economics of the National Football League, then Atomic Habits / Frankenstein. Sports failed “anything similar to that one” with an accepted incorrect intent (`RECOMMEND_AVAILABLE_SIMILAR` instead of `MORE_LIKE_THIS`). The second five-turn chain passed, partly through fallback. The live observer validates intent, references, requested fields and clarification; it did not independently judge every free-form criterion interpretation. Frozen semantic grading is stricter. Reported confidence below is the raw subtype head, not a probability that the entire answer is correct. Client elapsed time includes observer profile lookup; server trace timings are separately retained in JSON.\n\n' +
        table(['Chain', 'Turn', 'Result', 'CPU accepted', 'Subtype confidence', 'Qwen calls', 'Client ms', 'Resolved public IDs'], live_rows))
    add('AE', 'Live accounts', '3/4. “what books do I still have out?” failed through Qwen fallback. Fees, reservations and recent-history phrases passed with zero Qwen routing calls. Account data was read under each request’s authorization and was not persisted in reports.')
    add('AF', 'Live Search', '1/2. Beginner-friendly machine-learning request passed classifier-only. Saving/household-budgeting request failed through fallback. Existing Search query/ranking/pagination algorithms were unchanged. Final Search health still reports pre-existing degraded index state; HTTP remains 200.')
    add('AG', 'Page / previous comparison / selection change', 'Page 1/3: authors passed; availability and similar-books failed. Changing A+B to C+D passed the rating comparison (1/1). Clearing the tray after a valid comparison failed both previous-comparison follow-ups (0/2). Noise cases 1/2. Original test setup used invalid `COMPARE_SELECTED` with a null message; those two 422 setup calls and their dependent follow-ups were corrected using the real `COMPARE` contract and rechecked. Failed original attempts are retained separately. This observer repair changed neither model nor frozen evaluation. Concurrent own-pair query returned zero successful book responses across 20 requests, despite zero observed crossover.')
    con = data['concurrency']
    con_rows = [[n, f"{con['no_batching'][n]['median_ms']:.2f}", f"{con['no_batching'][n]['p95_ms']:.2f}", f"{con['no_batching'][n]['throughput_per_sec']:.2f}",
                 f"{con['micro_batching'][n]['median_ms']:.2f}", f"{con['micro_batching'][n]['p95_ms']:.2f}", f"{con['micro_batching'][n]['throughput_per_sec']:.2f}"] for n in ['1','5','10','20']]
    add('AH', 'CPU concurrency', table(['Concurrent', 'Default median ms', 'Default p95 ms', 'Default req/s', 'Batch median ms', 'Batch p95 ms', 'Batch req/s'], con_rows) +
        '\n\n80 requests per level per configuration, zero errors/Qwen/GPU-lock calls. Experimental micro-batching: max eight, 5 ms delay; measured sequentially with one encoder at a time. Both pass p95 <1 second at 20, both miss preferred <=500 ms. Default remains no batching. Queue and encoder timing plus CPU/RSS are in the concurrency JSON. These rates are classification throughput, not product capacity. No 744x capacity claim is made.')
    mixed = live['mixed_20']
    mixed_classifier = [r['classifier_ms'] for r in mixed['requests'] if r.get('classifier_ms') is not None]
    mixed_summary = {'classifier_samples': len(mixed_classifier), 'classifier_median_ms': float(np.median(mixed_classifier)),
                     'classifier_p95_ms': float(np.quantile(mixed_classifier, .95)),
                     'http_p95_ms': float(np.quantile([r['latency_ms'] for r in mixed['requests']], .95))}
    write('mixed_summary', mixed_summary)
    add('AI', 'Mixed 20-user load', f"Observed eligibility probes targeted 14 classifier-eligible and six fallback messages; the measured concurrent run accepted {mixed['accepted']}. HTTP completion successes {mixed['successes']}/20; busy rejections {mixed['busy_rejections']}; failures {mixed['failures']}; wall time {mixed['total_seconds']:.3f} s; completion throughput {mixed['throughput_per_sec']:.3f} requests/s. Classifier median/p95: {mixed_summary['classifier_median_ms']:.2f}/{mixed_summary['classifier_p95_ms']:.2f} ms ({len(mixed_classifier)} measurements); client HTTP p95 {mixed_summary['http_p95_ms']:.2f} ms. This is HTTP error/completion throughput, **not 16 semantically correct answers**. Existing Qwen admission remains bounded. Per-request classifier latency and busy status are retained.")
    add('AJ', 'HTTP contention root cause and fix', 'Creating 20 per-request `httpx.AsyncClient` instances took 7,804.59 ms synchronously (~388.36 ms median each), blocking the RAG event loop before useful tool work. A single lifespan client is now reused (40 max connections, 20 keep-alive; 40 s timeout/connect 3 s). Every request creates its own tool wrapper and passes its own bearer header; no shared user/auth defaults. Client shutdown closes it. Pool configuration and transport setup changed; tool/auth/callback contracts and algorithms did not. Exact trace-joined server timing excludes client-side profile-file lookup. See `assistant_router_v4_http_contention.md`.')
    coexist = live['rag_coexistence']
    coexist_rows = []
    for kind in ['document', 'book']:
        d = coexist[kind]
        traffic = d['classifier_traffic']
        coexist_rows.append([kind, d['status'], d['verdict'], len(traffic), sum(t['qwen_calls'] for t in traffic),
                              f"{np.quantile([t['server_total_ms'] for t in traffic], .95):.2f}",
                              f"{np.quantile([t['classifier_ms'] for t in traffic], .95):.2f}"])
    add('AK', 'RAG coexistence', table(['RAG', 'HTTP', 'Verdict', 'CPU requests', 'CPU Qwen calls', 'Server p95 ms', 'Classifier/gateway p95 ms'], coexist_rows) +
        '\n\n40/40 concurrent fees requests were accepted with zero Qwen routing calls. Document and authorized book RAG returned supported answers while classification continued. V3 coexistence server p95 was roughly eight seconds; V4 measured 742/842 ms after the client fix. Document owner upload returned 200; another user’s access returned 404; the disposable synthetic document was deleted. No permanent catalogue/circulation mutation was performed. RAG took ~18.75/21.63 seconds for its own generative responses; CPU throughput does not remove generative admission limits.')
    add('AL', 'Regression tests', '833 unique backend tests passed; 10 opt-in integration tests skipped. This equals 805 existing baseline/regression passes plus 28 V4 tests; later V4 runs replace duplicated tests and resolve the initial missing-corpus skip. Frontend: 85 assistant tests plus 47 Search-depth/KG/notification tests = 132 passes. Coverage includes assistant, security/session/ownership, staff/admin/notifications, circulation, Search pagination, recommendation/KG, Know More, book access and document RAG security. V4 tests cover serialization/current-message priority/redaction, loss masks, seed splitting/overlap, frozen guard, accepted/rejected Qwen counts, GPU-lock independence, concurrent owner state and mutation confirmation. Group counts/XML/logs are indexed in the regression JSON. Skipped checks are not claimed as passed.')
    add('AM', 'Build and lint', 'Production frontend build passed (TypeScript + Vite). Lint completed with zero errors and 19 existing warnings. No frontend source or ranking/algorithm implementation changed in V4.')
    modified = data['final_integrity']['changed_existing_files']
    source_added = ['assistant/router_v4.py', 'tests/test_assistant_router_v4.py', 'scripts/router_v4_data.py', 'scripts/generate_router_v4.py',
                    'scripts/prepare_router_v4.py', 'scripts/train_router_v4.py', 'scripts/select_router_v4.py', 'scripts/seal_router_v4.py',
                    'scripts/evaluate_router_v4.py', 'scripts/check_router_v4_live.py', 'scripts/audit_router_v4_completion.py', 'scripts/summarize_router_v4.py']
    add('AN', 'Exact changed files', 'Modified existing files:\n\n' + '\n'.join('- `' + p + '`' for p in modified) +
        '\n\n`api.py` adds opt-in modes and the reusable HTTP transport; `profiling.py` records V4 numeric timings; `qwen.py` updates only the busy response text; the document latency test normalizes the authorized HTTP-client wrapper change while retaining the remaining handler contract assertion.\n\nNew source/test files:\n\n' + '\n'.join('- `' + p + '`' for p in source_added) +
        '\n\nNew artifacts/data: `assistant/models/router_v4/`, `assistant/models/router_v4_candidates/`, `training/assistant_router_v4/`. New evidence is exclusively under `reports/assistant_router_v4*`, including the archived first V4 slot-coverage attempt. The complete recursive file inventory and hashes are in `assistant_router_v4_file_manifest.json`. Hash verification covers 3,245 baseline files: four authorized shared source/test files changed; no baseline file is missing; sealed runtime, artifact and manifest remain unchanged. The live upload/delete also changed `rag/private_documents/registry.sqlite` bytes; the registry contains zero rows after disposable-document removal. It was not restored from an old database snapshot. Original V3 source/data/evidence and Search/Recommendation/KG/RAG algorithms remain intact.')
    add('AO', 'Exact training command', 'Commands used before the final seal, from `D:\\SDC\\LibraryLLM`:\n\n```powershell\n.venv\\Scripts\\python.exe scripts/train_router_v4.py --output assistant/models/router_v4 --seed 947 --device cuda\n.venv\\Scripts\\python.exe scripts/select_router_v4.py --device cuda\n.venv\\Scripts\\python.exe scripts/seal_router_v4.py\n```\n\nThe corpus accept-list and seeds are versioned in the V4 training directory; framework versions/config/hashes are recorded. Reproduction must use a separate checkout/copy and fresh V4 report/candidate namespace. Do not run these commands against the completed experiment: the existing manifest guard refuses artifact replacement, while preparation/selection tools write their V4 evidence namespace. No reproduction training was run after the frozen evaluation. Numerical GPU nondeterminism can prevent byte-identical retraining.')
    add('AP', 'Exact evaluation command', 'The one-time command used after sealing:\n\n```powershell\n.venv\\Scripts\\python.exe scripts/evaluate_router_v4.py --frozen-test --concurrency\n```\n\n`--frozen-test` requires matching manifest/runtime seal and an absent exclusive started marker. That marker now exists and blocks another frozen execution. For new development, `--concurrency` alone does not inspect frozen text; use a fresh evidence namespace/copy for future benchmarks. Live experiment used `scripts/check_router_v4_live.py`; only the invalid context observer setup was repaired separately. There was no repeated frozen probing.')
    add('AQ', 'Start commands and restored state', 'Default RAG start (services are already running; do not start duplicates):\n\n```powershell\n$env:ASSISTANT_ROUTER_MODE = "existing_qwen"\n$env:ASSISTANT_ROUTER_V2_VARIANT = ""\n$env:ASSISTANT_ROUTER_V2_RETRY = "0"\n$env:ASSISTANT_PROFILE_PATH = "D:\\SDC\\LibraryLLM\\reports\\assistant_router_v4_restored_profiles.jsonl"\n.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1\n```\n\nOther existing services use `backend.main:app` on 8002, `search.api:app` on 8003, `recommendation.api:app` on 8004 and existing Vite on 5173. Experimental modes are supported through `ASSISTANT_ROUTER_MODE=router_v4` or `router_v4_shadow`; V3 modes remain supported too. **Neither V4 mode is enabled now.** Required offline gates failed, so conditional shadow validation was skipped. Restored typed comparison and natural first-book availability passed with no V4 telemetry; natural routing used existing Qwen. No router child remains. Health: Core/RAG healthy, Recommendation ready, frontend HTTP200, Search HTTP200/degraded (existing condition).')
    add('AR', 'Production recommendation', 'Keep `existing_qwen`. Do not promote either V3 or V4. Retain the reviewed HTTP transport fix and numeric telemetry integration. V4 demonstrates that small CPU inference can coexist with generative RAG, but its false accepts and unresolved contextual cases are unacceptable. The frozen data remains sealed; no new model or automatic follow-on experiment has been started.')
    add('AS', 'Known limitations', 'The experiment did not meet the complete language/data-distribution mission: most examples still have a single focus, only 1,083 unique messages underlie 15,162 cases, internal families share authored style, and manual review was performed by the agent rather than independent annotators. Critical previous-comparison, criterion and page semantics failed; explicit named entities still depend on existing Qwen extraction, which also failed some frozen cases. Higher acceptance is not safe capacity when precision is poor. Calibration uses correlated context variants and empirical thresholds without a population guarantee. Some all-case masked-head counters are not meaningful; relevant-only recomputations are reported above. Concurrent no-crossover checks returned no useful book responses. Mixed-load completion is not semantic accuracy. Optional integration tests were skipped; Search remains degraded and host RAM/commit headroom is limited. Timing reflects this Windows machine and its existing services; batching missed the preferred 500 ms p95 target. Shadow validation was correctly skipped. Frozen evaluations are complete once, the default is restored, and work stops here.')
    (REPORTS / 'assistant_router_v4_decision.md').write_text('# LuminaR Semantic Router V4 — final evaluation\n\n' + '\n'.join(sections), encoding='utf8')
    gap_rows = [[n, gap[n]['cases'], gap[n]['unique_messages'], gap[n]['unique_skeletons'], f"{gap[n]['words_mean']:.2f}", gap[n]['vocabulary'], f"{gap[n]['distinct_bigram_ratio']:.3f}"] for n in ['v3','v4','frozen_116','frozen_121']]
    (REPORTS / 'assistant_router_v4_dataset_gap.md').write_text('# V4 distribution audit\n\n' + gap['hypothesis'] + '\n\n' +
        table(['Corpus','Cases','Unique messages','Skeletons','Mean words','Vocabulary','Bigram ratio'],gap_rows) + '\n\n' + gap['remaining_gap'] +
        '\n\nSingle-focus fraction: V3 80.04%, V4 85.71%. Authority-state and tray-size variation did not remove this bias. Data is 14 context expansions per utterance; lexical diversity must be assessed on unique messages. Detailed syntax, intent, reference, position and context distributions plus descriptive shared embedding clusters are in the JSON. Frozen comparisons are audit-only and never labels used for training or threshold fitting. No model was changed after frozen evaluation.\n' + cluster_text + '\n', encoding='utf8')
    inventory = []
    paths = [ROOT / p for p in source_added + modified + data['final_integrity']['changed_runtime_files']]
    for directory in ['assistant/models/router_v4', 'assistant/models/router_v4_candidates', 'training/assistant_router_v4']:
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file()]
    paths += [p for p in REPORTS.rglob('*') if p.is_file() and p.relative_to(REPORTS).parts[0].startswith('assistant_router_v4')]
    for path in sorted(set(paths)):
        if path.name == 'assistant_router_v4_file_manifest.json':
            continue
        inventory.append({'path':path.relative_to(ROOT).as_posix(), 'bytes':path.stat().st_size,
                          'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                          'active_log':path.name.startswith('assistant_router_v4_restored') and path.suffix in {'.log','.jsonl'}})
    write('file_manifest', {'method':'Snapshot hashes; active service logs may append after this inventory. Includes V4 archive and baseline snapshots; existing modified sources explicitly listed.', 'files':inventory})
    print('FINAL REPORT', len(sections), 'A-AS sections; FAIL; inventory', len(inventory), flush=True)


if __name__ == '__main__':
    main()
