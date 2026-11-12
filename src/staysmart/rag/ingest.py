from collections.abc import Mapping
from pathlib import Path

import numpy as np

from staysmart.rag.chunking import chunk_document
from staysmart.rag.corpus import load_corpus
from staysmart.rag.embedder import Embedder
from staysmart.rag.errors import RagError
from staysmart.rag.index import VectorIndex


def build_index(
    corpus_path: Path,
    index_path: Path,
    embedder: Embedder,
    destination_by_hotel: Mapping[str, str] | None = None,
) -> VectorIndex:
    documents = load_corpus(corpus_path)
    if not documents:
        raise RagError(f"knowledge corpus at {corpus_path} contains no documents")
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    if destination_by_hotel:
        chunks = [
            chunk.model_copy(update={"destination_id": destination_by_hotel[chunk.hotel_id]})
            if chunk.hotel_id in destination_by_hotel
            else chunk
            for chunk in chunks
        ]
    vectors = embedder.embed_documents([chunk.embedded_text() for chunk in chunks])
    index = VectorIndex(np.asarray(vectors, dtype=np.float32), chunks)
    index.save(index_path)
    return index
