"""
Embeddings - Uses Gemini text-embedding-004 API.
No local model loaded — zero RAM overhead.
Dimension: 768 (text-embedding-004 default)
"""

import os
import numpy as np
from typing import List

EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIM   = 768

# Batch size — Gemini embedding API accepts up to 100 texts per call
_BATCH_SIZE = 50

_client = None

def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def _embed_batch_api(texts: List[str]) -> np.ndarray:
    """Call Gemini embedding API for a batch of texts."""
    client = _get_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
    )
    # result.embeddings is a list of ContentEmbedding objects
    vectors = np.array([e.values for e in result.embeddings], dtype="float32")
    return vectors


def embed_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype="float32")

    all_vecs = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i:i + _BATCH_SIZE]
        vecs = _embed_batch_api(batch)
        all_vecs.append(vecs)

    arr = np.vstack(all_vecs).astype("float32")

    if normalize:
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        arr = arr / norms

    return arr


def embed_query(query: str, normalize: bool = True) -> np.ndarray:
    return embed_texts([query], normalize=normalize)


def embed_batch(texts: List[str], batch_size: int = 50, normalize: bool = True) -> np.ndarray:
    return embed_texts(texts, normalize=normalize)


def get_embedding_dimension() -> int:
    return EMBEDDING_DIM


# Legacy — kept so rag_pipeline.py imports don't break
def get_model():
    class _Stub:
        def get_embedding_dimension(self):
            return EMBEDDING_DIM
    return _Stub()
