"""Configuration settings for FAISS implementation."""
import os

# Default embedding dimension
EMBEDDING_DIM = 384 

# Metric used for the index
METRIC = "IP" # Inner Product, assuming embeddings are normalized (cosine similarity)

# Paths
DEFAULT_OUTPUT_DIR = os.path.join("datasets", "ai", "faiss")
