"""
Embeddings - Uses FastEmbed (ONNX-based, no PyTorch/CUDA needed) for fast startup.
Model: BAAI/bge-small-en-v1.5 — 384 dims, ~130MB, CPU-only
"""

import numpy as np
from typing import List

MODEL_NAME = "BAAI/bge-small-en-v1.5"
_model = None


def get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=MODEL_NAME)
    return _model


def embed_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    model = get_model()
    embeddings = list(model.embed(texts))
    arr = np.array(embeddings, dtype="float32")
    if normalize:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        arr = arr / norms
    return arr


def embed_query(query: str, normalize: bool = True) -> np.ndarray:
    return embed_texts([query], normalize=normalize)


def embed_batch(texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
    return embed_texts(texts, normalize=normalize)


def get_embedding_dimension() -> int:
    # BAAI/bge-small-en-v1.5 produces 384-dim embeddings
    return 384
