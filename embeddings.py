"""
Embeddings - Uses SentenceTransformers with lazy loading for fast startup.
"""

import os, logging, warnings
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "3")
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import numpy as np
from typing import List

MODEL_NAME = "all-mpnet-base-v2"
_model = None


def get_model():
    global _model
    if _model is None:
        # Import only when first needed — keeps server startup fast
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_texts(texts: List[str], normalize: bool = True) -> np.ndarray:
    model = get_model()
    embeddings = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize
    )
    return embeddings.astype("float32")


def embed_query(query: str, normalize: bool = True) -> np.ndarray:
    return embed_texts([query], normalize=normalize)


def embed_batch(texts: List[str], batch_size: int = 32, normalize: bool = True) -> np.ndarray:
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=normalize
    )
    return embeddings.astype("float32")


