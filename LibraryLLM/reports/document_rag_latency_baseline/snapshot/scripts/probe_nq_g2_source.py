"""Probe the specified NQ source; never substitute a dataset or train."""
import json
import os
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'datasets/training/hf_cache/nq_g2'
os.environ['HF_HOME'] = str(CACHE)
os.environ['HF_DATASETS_CACHE'] = str(CACHE / 'datasets')
from huggingface_hub import HfApi, hf_hub_download
from datasets import get_dataset_config_names, load_dataset_builder

result = {'dataset_id': 'sentence-transformers/natural-questions',
          'url': 'https://huggingface.co/datasets/sentence-transformers/natural-questions',
          'cache': str(CACHE)}
try:
    info = HfApi().dataset_info(result['dataset_id'], timeout=20)
    result.update(revision=info.sha, gated=info.gated, private=info.private)
    result['card_path'] = hf_hub_download(result['dataset_id'], 'README.md',
        repo_type='dataset', revision=info.sha, cache_dir=str(CACHE / 'hub'))
    configs = get_dataset_config_names(result['dataset_id'], revision=info.sha)
    result['configs'] = configs
    for config in configs:
        builder = load_dataset_builder(result['dataset_id'], name=config,
            revision=info.sha, cache_dir=str(CACHE / 'datasets'))
        result.setdefault('schemas', {})[config] = {
            'features': str(builder.info.features), 'splits': str(builder.info.splits)}
    result['status'] = 'accessible'
except Exception as exc:
    result.update(status='FAILED_STOP', error_type=type(exc).__name__,
                  error=str(exc), traceback=traceback.format_exc())
(ROOT / 'datasets/training/reports/rag_g2_nq_source_probe_retry.json').write_text(
    json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
