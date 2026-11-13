from pathlib import Path

from staysmart.rag.corpus import corpus_fingerprint
from staysmart.rag.embedder import Embedder
from staysmart.rag.errors import RagError
from staysmart.rag.index import VectorIndex
from staysmart.rag.models import ContextBundle, ContextSource, RetrievedChunk


class RagRetriever:
    def __init__(self, index: VectorIndex, embedder: Embedder) -> None:
        self._index = index
        self._embedder = embedder

    @classmethod
    def load(cls, index_path: Path, embedder: Embedder, *, corpus_path: Path | None = None) -> "RagRetriever":
        index = VectorIndex.load(index_path)
        manifest = index.manifest
        if manifest is None:
            raise RagError(f"vector index at {index_path} has no manifest; run 'python -m staysmart.rag ingest' again")
        if manifest.model_name != embedder.model_id:
            raise RagError(
                f"index was built with embedding model {manifest.model_name!r} but the configured embedder is "
                f"{embedder.model_id!r}; run 'python -m staysmart.rag ingest' again"
            )
        if manifest.dim != embedder.dim:
            raise RagError(
                f"index dim {manifest.dim} does not match embedder dim {embedder.dim}; "
                "run 'python -m staysmart.rag ingest' again"
            )
        if corpus_path is not None and corpus_fingerprint(corpus_path) != manifest.corpus_hash:
            raise RagError(
                "knowledge corpus changed since the index was built; run 'python -m staysmart.rag ingest' again"
            )
        return cls(index, embedder)

    def retrieve(
        self,
        query: str,
        *,
        hotel_id: str | None = None,
        destination_id: str | None = None,
        category: str | None = None,
        top_k: int = 4,
    ) -> list[RetrievedChunk]:
        if not query or not query.strip():
            raise RagError("query must not be blank")
        query_vector = self._embedder.embed_query(query)
        hits = self._index.search(
            query_vector,
            hotel_id=hotel_id,
            destination_id=destination_id,
            category=category,
            top_k=top_k,
        )
        return [RetrievedChunk(chunk=chunk, score=score) for chunk, score in hits]

    def build_context(
        self,
        query: str,
        *,
        hotel_id: str | None = None,
        destination_id: str | None = None,
        category: str | None = None,
        top_k: int = 4,
        max_chars: int = 1200,
    ) -> ContextBundle:
        results = self.retrieve(
            query,
            hotel_id=hotel_id,
            destination_id=destination_id,
            category=category,
            top_k=top_k,
        )
        blocks: list[str] = []
        included: list[RetrievedChunk] = []
        total = 0
        for position, retrieved in enumerate(results, start=1):
            block = f"[{position}] {retrieved.chunk.formatted_block()}"
            if blocks and total + len(block) + 2 > max_chars:
                break
            blocks.append(block)
            included.append(retrieved)
            total += len(block) + 2

        sources: list[ContextSource] = []
        for retrieved in included:
            chunk = retrieved.chunk
            existing = next((source for source in sources if source.doc_id == chunk.doc_id), None)
            if existing is None:
                sources.append(
                    ContextSource(
                        doc_id=chunk.doc_id,
                        title=chunk.title,
                        category=chunk.category,
                        chunk_count=1,
                        hotel_id=chunk.hotel_id,
                        destination_id=chunk.destination_id,
                    )
                )
            else:
                existing.chunk_count += 1

        return ContextBundle(
            query=query,
            chunks=included,
            sources=sources,
            formatted_context="\n\n".join(blocks),
        )
