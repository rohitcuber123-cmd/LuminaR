"""Optional held-out generic sanity check; not the LuminaR selection metric."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import torch

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
DATA = TRAIN / "generic" / "msmarco_g1"
G1 = TRAIN / "models" / "minilm_g1_msmarco_50k_full"
OUT = TRAIN / "reports" / "rag_g1_msmarco_generic_validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(model_path: str, rows: list[dict]) -> dict:
    model = SentenceTransformer(model_path, device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    if model.max_seq_length != 256 or model.get_embedding_dimension() != 384:
        raise RuntimeError("Encoder architecture changed")
    wins = 0
    margins = []
    for first in range(0, len(rows), 64):
        batch = rows[first:first + 64]
        arrays = [model.encode([r[key] for r in batch], batch_size=64,
                               normalize_embeddings=True, convert_to_numpy=True,
                               show_progress_bar=False)
                  for key in ("query", "positive", "negative")]
        margin = np.sum(arrays[0] * arrays[1], axis=1) - np.sum(arrays[0] * arrays[2], axis=1)
        wins += int(np.sum(margin > 0))
        margins.extend(float(x) for x in margin)
    return {"pairwise_accuracy": wins / len(rows), "mean_positive_minus_negative": float(np.mean(margins))}


def main() -> None:
    if OUT.exists():
        raise FileExistsError(OUT)
    data = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    path = DATA / "msmarco_g1_validation.parquet"
    if sha(path) != data["files"]["validation"]["sha256"]:
        raise RuntimeError("Validation hash changed")
    rows = pq.read_table(path).to_pylist()
    if len(rows) != 5000 or data["quality"]["train_validation_query_overlap"]:
        raise RuntimeError("Invalid held-out split")
    base_path = json.loads((TRAIN / "manifests" / "minilm_generic_pilot_v1.json").read_text(encoding="utf-8"))["base_model"]
    result = {"experiment": "G1_MS_MARCO", "role": "optional generic sanity; not LuminaR selection",
              "heldout_rows": len(rows), "test_evaluated": False,
              "baseline": score(base_path, rows), "g1": score(str(G1), rows)}
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
