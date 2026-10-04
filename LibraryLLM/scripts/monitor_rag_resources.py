"""Sample real GPU/CPU resources for a benchmark process until it exits."""
import argparse
import json
import subprocess
import time
from pathlib import Path
import psutil

p = argparse.ArgumentParser()
p.add_argument('pid', type=int)
p.add_argument('output')
p.add_argument('--seconds', type=float, default=float('inf'))
args = p.parse_args()
proc = psutil.Process(args.pid)
rows = []
proc.cpu_percent()
started = time.monotonic()
while proc.is_running() and time.monotonic() - started < args.seconds:
    try:
        sample = {'time': time.time(), 'cpu_percent': proc.cpu_percent(),
                  'rss_mb': proc.memory_info().rss / 2**20,
                  'available_ram_mb': psutil.virtual_memory().available / 2**20}
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total',
                              '--format=csv,noheader,nounits'], capture_output=True, text=True,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if gpu.returncode == 0:
            sample['gpu_util_percent'], sample['gpu_memory_mb'], sample['gpu_total_mb'] = map(float, gpu.stdout.strip().split(','))
        rows.append(sample)
        Path(args.output).write_text(json.dumps(rows, indent=2), encoding='utf-8')
        time.sleep(1)
    except psutil.NoSuchProcess:
        break
