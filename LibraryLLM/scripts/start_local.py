"""Supervise the real local services; Ctrl+C stops only children started here."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT/'.env')
from scripts.local_seed import local_guard
local_guard()

parser = argparse.ArgumentParser()
parser.add_argument('--models', type=Path, default=ROOT/'.local/hf-cache')
parser.add_argument('--mongo-data', type=Path, default=ROOT/'.local/mongodb')
parser.add_argument('--mongod', default=shutil.which('mongod'))
args = parser.parse_args()
os.environ['HF_HOME'] = str(args.models.resolve())
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['LUMINAR_MOCK_LLM'] = '0'
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('MKL_NUM_THREADS', '4')
logs = ROOT/'.local/logs'; logs.mkdir(parents=True, exist_ok=True)
children, handles = [], []

def listening(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(('127.0.0.1',port)) == 0

def launch(name, port, command, cwd=ROOT):
    if listening(port):
        print(f'{name}: port {port} already in use; keeping the existing service.', flush=True)
        return
    handle = (logs/f'{name}.log').open('a', encoding='utf-8')
    handles.append(handle)
    process = subprocess.Popen(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    children.append((name,process))
    print(f'{name}: starting on {port}, log {logs/name}.log', flush=True)

try:
    if not listening(27017):
        if not args.mongod and os.name == 'nt':
            candidates = sorted(Path('C:/Program Files/MongoDB/Server').glob('*/bin/mongod.exe'))
            args.mongod = str(candidates[-1]) if candidates else None
        if not args.mongod:
            raise SystemExit('MongoDB Server is required. Supply --mongod with its executable path.')
        args.mongo_data.mkdir(parents=True, exist_ok=True)
        launch('mongodb',27017,[args.mongod,'--dbpath',str(args.mongo_data.resolve()),'--bind_ip','127.0.0.1','--port','27017'])
        for _ in range(60):
            if listening(27017):break
            time.sleep(.5)
        if not listening(27017):raise RuntimeError('MongoDB did not start; inspect its log.')
    for name,module,port in [('core','backend.main',8002),('search','search.api',8003),
                             ('recommendation','recommendation.api',8004),('rag','rag.api',8005)]:
        launch(name,port,[sys.executable,'-m','uvicorn',module+':app','--host','127.0.0.1','--port',str(port)])
    node = shutil.which('node')
    vite = ROOT/'frontend/node_modules/vite/bin/vite.js'
    if not node or not vite.exists():raise RuntimeError('Node.js and frontend npm ci are required.')
    # Direct child instead of npm.cmd so Ctrl+C cleanup also stops Vite on Windows.
    launch('frontend',5173,[node,str(vite),'--host','127.0.0.1','--port','5173','--strictPort'],ROOT/'frontend')
    print('Open http://127.0.0.1:5173/ . Initial Qwen loading may take several minutes.',flush=True)
    print('Leave this terminal running. Ctrl+C stops the services started by this launcher.',flush=True)
    while True:
        for name,process in children:
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited ({process.returncode}); inspect {logs/name}.log')
        time.sleep(2)
except KeyboardInterrupt:
    print('Stopping local services...',flush=True)
finally:
    for name,process in reversed(children):
        if process.poll() is None:process.terminate()
    for name,process in reversed(children):
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill()
    for handle in handles:handle.close()
