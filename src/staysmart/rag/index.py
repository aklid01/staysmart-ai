import json
from pathlib import Path

import numpy as np

from staysmart.rag.errors import RagError
from staysmart.rag.models import KnowledgeChunk


class VectorIndex:
    def __init__(self, vectors: np.ndarray, chunks: list[KnowledgeChunk]) -> None:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            raise RagError(f"vector/chunk count mismatch: {matrix.shape[0]} vectors for {len(chunks)} chunks")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self.vectors = matrix / norms
        self.chunks = list(chunks)

    @property
    def dim(self) -> int:
        return int(self.vectors.shape[1])

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def search(
        self,
        query_vector: list[float] | np.ndarray,
        *,
        hotel_id: str | None = None,
        destination_id: str | None = None,
        category: str | None = None,
        top_k: int = 4,
    ) -> list[tuple[KnowledgeChunk, float]]:
        if top_k < 1:
            raise RagError("top_k must be at least 1")
        query = np.asarray(query_vector, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if norm > 0.0:
            query = query / norm

        candidates = [
            i
            for i, chunk in enumerate(self.chunks)
            if (hotel_id is None or chunk.hotel_id == hotel_id)
            and (destination_id is None or chunk.destination_id == destination_id)
            and (category is None or chunk.category == category)
        ]
        if not candidates:
            return []
        scores = self.vectors[candidates] @ query
        order = np.argsort(-scores, kind="stable")[:top_k]
        return [(self.chunks[candidates[i]], round(float(scores[i]), 4)) for i in order]

    def save(self, index_path: Path) -> None:
        index_path.mkdir(parents=True, exist_ok=True)
        np.save(index_path / "vectors.npy", self.vectors)
        payload = json.dumps([chunk.model_dump() for chunk in self.chunks], indent=2, ensure_ascii=False)
        (index_path / "chunks.json").write_text(payload + "\n", encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, index_path: Path) -> "VectorIndex":
        vectors_file = index_path / "vectors.npy"
        chunks_file = index_path / "chunks.json"
        if not vectors_file.is_file() or not chunks_file.is_file():
            raise RagError(f"vector index not found at {index_path}; run 'python -m staysmart.rag ingest' first")
        vectors = np.load(vectors_file)
        records = json.loads(chunks_file.read_text(encoding="utf-8"))
        chunks = [KnowledgeChunk.model_validate(record) for record in records]
        return cls(vectors, chunks)
