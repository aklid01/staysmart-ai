import pytest

from staysmart.rag.embedder import DeterministicEmbedder
from staysmart.rag.errors import RagError
from staysmart.rag.ingest import build_index
from staysmart.rag.service import RagRetriever


def test_retrieve_returns_metadata_and_four_decimal_scores(retriever):
    results = retriever.retrieve("dogs at the townhouse", hotel_id="hotel-kyo-01", top_k=3)

    assert len(results) == 3
    for retrieved in results:
        assert retrieved.chunk.hotel_id == "hotel-kyo-01"
        assert retrieved.score == round(retrieved.score, 4)
        assert retrieved.chunk.chunk_id
        assert retrieved.chunk.source_path.startswith("hotels/")


def test_retrieve_with_blank_query_raises(retriever):
    with pytest.raises(RagError, match="blank"):
        retriever.retrieve("   ")


def test_retrieve_with_impossible_filter_returns_empty(retriever):
    assert retriever.retrieve("anything", hotel_id="hotel-zzz-00") == []


def test_retrieve_respects_destination_filter(retriever):
    results = retriever.retrieve("when can we arrive", destination_id="kyoto-jp")

    assert len(results) >= 1
    for retrieved in results:
        assert retrieved.chunk.destination_id == "kyoto-jp"


def test_build_context_formats_numbered_blocks_and_sources(retriever):
    bundle = retriever.build_context("dogs at the townhouse", hotel_id="hotel-kyo-01", top_k=3, max_chars=4000)

    assert bundle.query == "dogs at the townhouse"
    assert len(bundle.chunks) == 3
    assert bundle.formatted_context.startswith("[1]")
    for number, retrieved in enumerate(bundle.chunks, start=1):
        assert f"[{number}] {retrieved.chunk.title} - {retrieved.chunk.heading}" in bundle.formatted_context

    assert bundle.sources
    first_seen = []
    for source in bundle.sources:
        assert source.chunk_count >= 1
        first_seen.append(source.doc_id)
    assert len(first_seen) == len(set(first_seen))
    total = sum(source.chunk_count for source in bundle.sources)
    assert total == len(bundle.chunks)


def test_build_context_truncates_at_chunk_boundaries(retriever):
    bundle = retriever.build_context("dogs at the townhouse", hotel_id="hotel-kyo-01", top_k=4, max_chars=400)

    assert len(bundle.formatted_context) <= 400 + len(bundle.chunks[0].formatted_block())
    assert len(bundle.chunks) >= 1
    assert len(bundle.chunks) < 4


def test_persisted_index_reloads_for_retrieval(stub_index, tmp_path):
    embedder = DeterministicEmbedder()
    loaded = RagRetriever.load(tmp_path / "index", embedder)

    results = loaded.retrieve("dogs at the townhouse", hotel_id="hotel-kyo-01", top_k=2)

    assert len(results) == 2
    direct = RagRetriever(stub_index, embedder).retrieve("dogs at the townhouse", hotel_id="hotel-kyo-01", top_k=2)
    assert [r.chunk.chunk_id for r in results] == [r.chunk.chunk_id for r in direct]


def test_ingest_into_empty_corpus_fails(tmp_path):
    empty = tmp_path / "corpus"
    empty.mkdir()

    with pytest.raises(RagError, match="no documents"):
        build_index(empty, tmp_path / "index", DeterministicEmbedder())
