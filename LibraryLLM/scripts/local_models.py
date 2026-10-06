"""Download the exact local models used by the existing engines."""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('HF_HOME', str(ROOT/'.local/hf-cache'))
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import snapshot_download
import huggingface_hub.file_download as files
if os.name == 'nt':
    files.are_symlinks_supported = lambda cache_dir=None: False
for model in ('sentence-transformers/all-MiniLM-L6-v2', 'cross-encoder/ms-marco-MiniLM-L-6-v2', 'Qwen/Qwen2.5-3B-Instruct'):
    print('Preparing', model, flush=True)
    snapshot_download(model, allow_patterns=['*.json','*.txt','*.safetensors','*.model'], max_workers=3)
    print('Ready:', model, flush=True)
