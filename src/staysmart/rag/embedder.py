import hashlib
from collections.abc import Sequence
from typing import Protocol

import numpy as np

DEFAULT_RAG_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


class Embedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


class FastEmbedEmbedder:
    def __init__(self, model_name: str = DEFAULT_RAG_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self._model_name)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        vectors = [np.asarray(vector, dtype=np.float32) for vector in model.embed(list(texts))]
        return [_normalize(vector).tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class DeterministicEmbedder:
    DIM = 64

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

    def _embed_one(self, text: str) -> list[float]:
        vector = np.zeros(self.DIM, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self.DIM
            vector[index] += 1.0 + digest[8] / 255.0
        if float(np.linalg.norm(vector)) == 0.0:
            vector[0] = 1.0
        return _normalize(vector).tolist()
