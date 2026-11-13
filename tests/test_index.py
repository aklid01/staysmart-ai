import numpy as np
import pytest

from staysmart.rag.embedder import DeterministicEmbedder
from staysmart.rag.errors import RagError
from staysmart.rag.index import VectorIndex

DIM = DeterministicEmbedder.DIM


def test_save_and_load_round_trip_is_exact(stub_index, tmp_path):
    reloaded = VectorIndex.load(tmp_path / "index")

    assert reloaded.chunk_count == stub_index.chunk_count
    assert reloaded.dim == stub_index.dim
    assert np.allclose(reloaded.vectors, stub_index.vectors, atol=1e-6)
    assert [chunk.chunk_id for chunk in reloaded.chunks] == [chunk.chunk_id for chunk in stub_index.chunks]


def test_load_missing_index_raises(tmp_path):
    with pytest.raises(RagError, match="not found"):
        VectorIndex.load(tmp_path / "missing")


def test_load_with_mismatched_counts_raises(tmp_path):
    index_path = tmp_path / "broken"
    index_path.mkdir()
    np.save(index_path / "vectors.npy", np.zeros((2, DIM), dtype=np.float32))
    (index_path / "chunks.json").write_text("[]", encoding="utf-8")

    with pytest.raises(RagError, match="mismatch"):
        VectorIndex.load(index_path)


def test_hotel_chunks_carry_dataset_destination(stub_index):
    van_chunks = [chunk for chunk in stub_index.chunks if chunk.hotel_id == "hotel-van-01"]

    assert van_chunks
    assert all(chunk.destination_id == "vancouver-ca" for chunk in van_chunks)
    destination_chunks = [chunk for chunk in stub_index.chunks if chunk.doc_id == "vancouver-ca-check-in-check-out"]
    assert all(chunk.hotel_id is None for chunk in destination_chunks)


def test_search_respects_hotel_filter(stub_index, embedder=None):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("pet policy for the lodge")
    results = stub_index.search(query, hotel_id="hotel-van-03", top_k=5)

    assert 0 < len(results) <= 5
    for chunk, _score in results:
        assert chunk.hotel_id == "hotel-van-03"


def test_search_respects_category_filter(stub_index):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("anything at all")
    results = stub_index.search(query, category="cancellation", top_k=8)

    assert len(results) > 0
    assert {chunk.category for chunk, _score in results} == {"cancellation"}


def test_search_combines_hotel_and_category_filters(stub_index):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("staying with a dog")
    results = stub_index.search(query, hotel_id="hotel-kyo-01", category="pet_policy")

    assert len(results) >= 1
    for chunk, _score in results:
        assert chunk.hotel_id == "hotel-kyo-01"
        assert chunk.category == "pet_policy"


def test_search_orders_scores_descending_and_rounds_to_four_decimals(stub_index):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("breakfast and wifi")
    results = stub_index.search(query, top_k=6)

    assert len(results) == 6
    scores = [score for _chunk, score in results]
    assert scores == sorted(scores, reverse=True)
    assert all(score == round(score, 4) for score in scores)


def test_search_with_unknown_hotel_returns_empty(stub_index):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("anything")
    assert stub_index.search(query, hotel_id="hotel-zzz-00") == []


def test_search_normalizes_query_vector(stub_index):
    embedder = DeterministicEmbedder()
    query = embedder.embed_query("breakfast and wifi")
    scaled = [value * 7.5 for value in query]
    direct = stub_index.search(query, top_k=3)
    scaled_result = stub_index.search(scaled, top_k=3)

    assert [chunk.chunk_id for chunk, _s in scaled_result] == [chunk.chunk_id for chunk, _s in direct]
