"""Observe the sole production service; no models, benchmarks or router imports."""
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'

def windows_memory():
    command = ('Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory | '
               'Select-Object AvailableMBytes,CommittedBytes,CommitLimit,PagesInputPersec,PageReadsPersec | ConvertTo-Json')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def main():
    startup = json.loads((REPORTS/'assistant_production_profiles.jsonl.runtime.json').read_text(encoding='utf8'))
    process = psutil.Process(startup['pid'])
    cmd = process.cmdline()
    assert 'rag.api:app' in cmd and startup['router_mode'] == 'existing_qwen'
    assert startup['experimental_router_modules'] == []
    samples = []
    for _ in range(3):
        sample = windows_memory()
        sample.update(process_rss_bytes=process.memory_info().rss,
            children=[{'pid': p.pid, 'name': p.name()} for p in process.children(recursive=True)])
        samples.append(sample)
        time.sleep(.2)
    profiles = [json.loads(line) for line in (REPORTS/'assistant_production_profiles.jsonl').read_text(encoding='utf8').splitlines()]
    last = profiles[-1].get('memory', {})
    services = {}
    for port in [8002, 8003, 8004, 8005, 5173]:
        listeners = {c.pid for c in psutil.net_connections(kind='tcp') if c.status == 'LISTEN' and c.laddr.port == port}
        services[str(port)] = sorted(listeners)
        assert len(listeners) == 1, f'Duplicate/missing listener on {port}'
    archived = json.loads((REPORTS/'assistant_router_v5_resources.json').read_text(encoding='utf8'))
    out = {'startup': startup, 'idle_samples': samples, 'last_request_gpu_and_rss_mb': last,
        'services': services, 'rejected_router_loaded': False,
        'rejected_router_child_processes': sum(len(r['children']) for r in samples),
        'minimum_idle_available_mib': min(r['AvailableMBytes'] for r in samples),
        'maximum_idle_commit_ratio': max(r['CommittedBytes']/r['CommitLimit'] for r in samples),
        'maximum_idle_pages_input_per_sec': max(r['PagesInputPersec'] for r in samples),
        'archived_v5_worker_rss_mib': archived['worker']['rss_before_verifier_mb'],
        'archived_v5_minimum_available_mib': 228,
        'comparison': 'Archived V5 evidence only; not a paired benchmark. No rejected router was launched. '
            'Normal RAG retains its own Qwen/retrieval/reranker models. Startup psutil swap metrics are raw swap observations; '
            'Windows commit is measured explicitly by WMI in idle_samples.',
        'note': 'Host commit remains high. No claim that removing the rejected worker fixes all full-stack memory pressure.'}
    (REPORTS/'assistant_production_memory.json').write_text(json.dumps(out, indent=2), encoding='utf8')
    print('MEMORY startup_RSS_MiB', round(startup['process_rss_bytes']/1048576,2),
          'idle_available_MiB', out['minimum_idle_available_mib'],
          'commit_percent', round(out['maximum_idle_commit_ratio']*100,2),
          'children', out['rejected_router_child_processes'])

if __name__ == '__main__':
    main()
