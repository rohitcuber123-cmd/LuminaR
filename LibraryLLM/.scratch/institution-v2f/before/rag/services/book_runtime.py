"""Refresh changed book assets under the engine's existing inference lock."""
from rag.book_assets import index_revision


class BookRuntime:
    def __init__(self, retriever, loaded_revision=None):
        self.retriever = retriever
        self.revision = loaded_revision if loaded_revision is not None else index_revision()

    def refresh(self):
        current = index_revision()
        if current == self.revision:
            return
        # No model reload, PDF index change, or retrieval/generation here.
        self.retriever._load_global_index()
        self.retriever._load_global_metadata()
        self.retriever._load_chunk_texts()
        self.retriever.book_index_cache.clear()
        self.revision = current
