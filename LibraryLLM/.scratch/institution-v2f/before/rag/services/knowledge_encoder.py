"""One cached CPU encoder for study deduplication; no Search or shared GPU state."""
from threading import Lock

_model = None
_lock = Lock()


def _load():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',
                                     device='cpu', local_files_only=True)


def prepare():
    """Load the existing CPU singleton before interactive grading is admitted."""
    with _lock:
        _load()


def encode(texts):
    with _lock:
        _load()
        return _model.encode(texts, batch_size=32, normalize_embeddings=True,
                             show_progress_bar=False, convert_to_numpy=True)
