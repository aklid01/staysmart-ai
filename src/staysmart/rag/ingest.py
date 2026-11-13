from collections.abc import Mapping
from pathlib import Path

import numpy as np

from staysmart.rag.chunking import chunk_document
from staysmart.rag.corpus import corpus_fingerprint, load_corpus
from staysmart.rag.embedder import Embedder
from staysmart.rag.errors import RagError
from staysmart.rag.index import SCHEMA_VERSION, IndexManifest, VectorIndex


def build_index(
    corpus_path: Path,
    index_path: Path,
    embedder: Embedder,
    destination_by_hotel: Mapping[str, str],
) -> VectorIndex:
    documents = load_corpus(corpus_path)
    if not documents:
        raise RagError(f"knowledge corpus at {corpus_path} contains no documents")
    chunks = [chunk for document in documents for chunk in chunk_document(document)]
    unmapped = sorted(
        {chunk.hotel_id for chunk in chunks if chunk.hotel_id and chunk.hotel_id not in destination_by_hotel}
    )
    if unmapped:
        raise RagError(f"corpus hotel documents missing from the dataset mapping: {', '.join(unmapped)}")
    chunks = [
        chunk.model_copy(update={"destination_id": destination_by_hotel[chunk.hotel_id]}) if chunk.hotel_id else chunk
        for chunk in chunks
    ]
    vectors = embedder.embed_documents([chunk.embedded_text() for chunk in chunks])
    index = VectorIndex(np.asarray(vectors, dtype=np.float32), chunks)
    manifest = IndexManifest(
        schema_version=SCHEMA_VERSION,
        model_name=embedder.model_id,
        dim=index.dim,
        chunk_count=index.chunk_count,
        corpus_hash=corpus_fingerprint(corpus_path),
    )
    index.save(index_path, manifest)
    return index
