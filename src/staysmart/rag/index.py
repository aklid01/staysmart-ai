import json
import os
from pathlib import Path

import numpy as np

from staysmart.domain.base import StrictModel
from staysmart.rag.errors import RagError
from staysmart.rag.models import KnowledgeChunk

SCHEMA_VERSION = 1


class IndexManifest(StrictModel):
    schema_version: int
    model_name: str
    dim: int
    chunk_count: int
    corpus_hash: str


class VectorIndex:
    def __init__(self, vectors: np.ndarray, chunks: list[KnowledgeChunk]) -> None:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
            raise RagError(f"vector/chunk count mismatch: {matrix.shape[0]} vectors for {len(chunks)} chunks")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self.vectors = matrix / norms
        self.chunks = list(chunks)
        self.manifest: IndexManifest | None = None

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

    def save(self, index_path: Path, manifest: IndexManifest) -> None:
        index_path.mkdir(parents=True, exist_ok=True)
        vectors_tmp = index_path / "vectors.tmp.npy"
        with open(vectors_tmp, "wb") as handle:
            np.save(handle, self.vectors)
        chunks_tmp = index_path / "chunks.tmp.json"
        chunks_tmp.write_text(
            json.dumps([chunk.model_dump() for chunk in self.chunks], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest_tmp = index_path / "manifest.tmp.json"
        manifest_tmp.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        os.replace(vectors_tmp, index_path / "vectors.npy")
        os.replace(chunks_tmp, index_path / "chunks.json")
        os.replace(manifest_tmp, index_path / "manifest.json")

    @classmethod
    def load(cls, index_path: Path) -> "VectorIndex":
        vectors_file = index_path / "vectors.npy"
        chunks_file = index_path / "chunks.json"
        manifest_file = index_path / "manifest.json"
        missing = [
            name
            for name, file in (
                ("vectors.npy", vectors_file),
                ("chunks.json", chunks_file),
                ("manifest.json", manifest_file),
            )
            if not file.is_file()
        ]
        if missing:
            raise RagError(
                f"vector index not found at {index_path} (missing {', '.join(missing)}); "
                "run 'python -m staysmart.rag ingest' first"
            )
        try:
            manifest = IndexManifest.model_validate(json.loads(manifest_file.read_text(encoding="utf-8")))
            vectors = np.load(vectors_file)
            records = json.loads(chunks_file.read_text(encoding="utf-8"))
            chunks = [KnowledgeChunk.model_validate(record) for record in records]
        except (OSError, ValueError, EOFError) as exc:
            raise RagError(
                f"vector index at {index_path} is unreadable ({exc}); run 'python -m staysmart.rag ingest' again"
            ) from exc
        if manifest.schema_version != SCHEMA_VERSION:
            raise RagError(
                f"index schema version {manifest.schema_version} is not supported (expected {SCHEMA_VERSION}); "
                "run 'python -m staysmart.rag ingest' again"
            )
        if manifest.chunk_count != len(chunks):
            raise RagError(
                f"vector index at {index_path} is inconsistent: manifest records {manifest.chunk_count} chunks "
                f"for {len(chunks)} chunks; run 'python -m staysmart.rag ingest' again"
            )
        index = cls(vectors, chunks)
        index.manifest = manifest
        return index
