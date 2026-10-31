"""One frozen, gold-blind disabled-candidate capture. Does not import an evaluator or gold."""
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import os
import sys
import time

R = Path('reports')
P = 'search_v2c_smarteng_c5c_'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def main():
    config_path = R / (P + 'parser_configuration.json')
    config = json.loads(config_path.read_text(encoding='utf8'))
    expected_count = config['prediction_calls_planned']
    inputs_path = R / (P + 'parser_inputs.jsonl')
    caps_path = Path(config['caps_path'])
    assert sha(inputs_path) == config['input_sha256'] and sha(caps_path) == config['caps_sha256']
    assert all(sha(p) == h for p, h in config['parser_source_hashes'].items())
    assert all(sha(p) == h for p, h in config['frozen_before_prediction_scripts'].items())
    inputs = [json.loads(s) for s in inputs_path.read_text(encoding='utf8').splitlines()]
    assert len(inputs) == expected_count and all(set(x) == {'case_id','query_text','scope_type','workspace_type','search_mode'} for x in inputs)
    caps = json.loads(caps_path.read_text(encoding='utf8'))['scopes']
    report_dir = R.resolve()
    permitted_reads = {inputs_path.resolve(), caps_path.resolve(), config_path.resolve()}
    reads, denied = set(), []

    def audit(event, args):
        if event in {'socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system', 'os.spawn'}:
            denied.append({'event': event})
            raise RuntimeError('C5C isolation forbids network/process operations: ' + event)
        if event == 'import' and str(args[0]).split('.')[0] in {'search','pymongo','requests','httpx','backend','assistant','rag','recommendation','sqlite3'}:
            denied.append({'event': event, 'module': str(args[0])})
            raise RuntimeError('C5C isolation forbids application/database imports')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            mode, flags = args[1], args[2]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing:
                if path.parent != report_dir or not path.name.startswith(P):
                    denied.append({'event': event, 'path': str(path), 'write': True})
                    raise RuntimeError('C5C only permits new C5C report writes')
            elif report_dir in path.parents and path not in permitted_reads:
                denied.append({'event': event, 'path': str(path), 'write': False})
                raise RuntimeError('Prediction process cannot read corpus, gold, review or historical reports')
            else:
                reads.add(str(path))
        if event in {'os.remove','os.rename','os.rmdir','os.mkdir','os.truncate'}:
            denied.append({'event': event})
            raise RuntimeError('C5C prediction process forbids filesystem mutations other than new reports')

    sys.addaudithook(audit)
    started = datetime.now(timezone.utc).isoformat()
    with (R / (P + 'prediction_started.json')).open('x', encoding='utf8') as out:
        json.dump({'started_at_utc': started, 'planned_calls': expected_count, 'attempt': 1,
                   'configuration_sha256': digest(config), 'input_sha256': config['input_sha256'],
                   'gold_available_to_prediction_process': False, 'retries': 0}, out, indent=2)
    # Same pure call chain as the established C5 evaluator. No execution/interaction API.
    from scratch.search_smart_engineering.parser import parse_query, PARSER_VERSION
    from scratch.search_smart_engineering.parser import validate, executable
    from scratch.search_smart_engineering.parser import assess
    count = errors = 0
    output_hash = hashlib.sha256()
    with (R / (P + 'predictions.jsonl')).open('xb') as out:
        for value in inputs:
            t = time.perf_counter()
            record = {'case_id': value['case_id'], 'input_sha256': digest(value), 'attempt': 1,
                      'scope_supplied': value['scope_type'], 'workspace_supplied': value['workspace_type'], 'mode': value['search_mode']}
            count += 1
            try:
                scope = caps[value['scope_type']]
                plan = validate(parse_query(value['query_text'], scope['subjects'], value['search_mode']), scope['capabilities'])
                actual = asdict(plan)
                actual['semantic_text'] = plan.semantic_text or ''
                actual['soft_preference'] = [] if not plan.soft_preference else [plan.soft_preference]
                record.update(status='CAPTURED', parser_version=PARSER_VERSION, actual_plan=actual,
                              typed_decision=plan.decision.get('decision_type', 'EXECUTABLE'), executable=executable(plan),
                              assessment=assess(plan), native_interpretation_confidence=plan.interpretation_confidence)
                record['output_sha256'] = digest({k: record[k] for k in ['actual_plan','typed_decision','executable','assessment','native_interpretation_confidence']})
            except Exception as error:
                errors += 1
                record.update(status='PARSER_OR_RUNTIME_ERROR', error_type=type(error).__name__, error=str(error))
                record['output_sha256'] = digest({k: record[k] for k in ['status','error_type','error']})
            record['elapsed_ms'] = (time.perf_counter() - t) * 1000
            encoded = (json.dumps(record, sort_keys=True, ensure_ascii=False) + '\n').encode('utf8')
            output_hash.update(encoded)
            out.write(encoded)
            out.flush()
    with (R / (P + 'prediction_complete.json')).open('x', encoding='utf8') as out:
        json.dump({'started_at_utc': started, 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                   'parser_calls': count, 'captured': count-errors, 'errors': errors, 'retries': 0,
                   'prediction_sha256': output_hash.hexdigest(),
                   'gold_reads': 0, 'network_calls': 0, 'isolation_denials': denied,
                   'files_read_after_isolation': sorted(reads), 'model_inferences': 0,
                   'limitation': 'One deterministic implementation run; no repeatability rerun performed.'}, out, sort_keys=True, indent=2)
    print(json.dumps({'parser_calls': count, 'captured': count-errors, 'errors': errors, 'retries': 0, 'isolation_denials': len(denied)}))

if __name__ == '__main__':
    main()
