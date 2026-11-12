import pytest

from staysmart.providers.mock.dataset import load_dataset
from staysmart.rag.corpus import load_corpus
from staysmart.rag.errors import RagError

CATEGORY_BY_FILENAME = {
    "general.md": "general",
    "rooms.md": "rooms",
    "amenities.md": "amenities",
    "cancellation.md": "cancellation",
    "pet-policy.md": "pet_policy",
    "check-in-check-out.md": "check_in_check_out",
}

HOTEL_CATEGORIES = {"general", "rooms", "amenities", "cancellation", "pet_policy"}
DESTINATION_CATEGORIES = {"check_in_check_out"}


def test_load_corpus_returns_53_sorted_documents(corpus_path):
    docs = load_corpus(corpus_path)

    assert len(docs) == 53
    paths = [doc.source_path for doc in docs]
    assert paths == sorted(paths)
    assert paths[0] == "destinations/kyoto-jp/check-in-check-out.md"
    assert paths[-1] == "hotels/hotel-van-03/rooms.md"


def test_every_dataset_hotel_has_five_docs_and_every_destination_one(corpus_path, settings):
    docs = load_corpus(corpus_path)
    dataset = load_dataset(settings.dataset_path)
    by_hotel = {}
    by_destination = {}
    for doc in docs:
        if doc.hotel_id:
            by_hotel.setdefault(doc.hotel_id, []).append(doc.category)
        if doc.destination_id:
            by_destination.setdefault(doc.destination_id, []).append(doc.category)

    assert set(by_hotel) == {hotel.hotel_id for hotel in dataset.hotels}
    assert set(by_destination) == {destination.destination_id for destination in dataset.destinations}
    for hotel_id, categories in by_hotel.items():
        assert set(categories) == HOTEL_CATEGORIES
        assert len(categories) == 5
    for destination_id, categories in by_destination.items():
        assert set(categories) == DESTINATION_CATEGORIES


def test_frontmatter_category_matches_filename(corpus_path):
    for doc in load_corpus(corpus_path):
        filename = doc.source_path.rsplit("/", 1)[1]
        assert doc.category == CATEGORY_BY_FILENAME[filename]


def test_doc_ids_are_unique(corpus_path):
    docs = load_corpus(corpus_path)
    assert len({doc.doc_id for doc in docs}) == len(docs)


def test_hotel_docs_carry_hotel_id_only_and_destination_docs_the_reverse(corpus_path):
    for doc in load_corpus(corpus_path):
        if doc.category in HOTEL_CATEGORIES:
            assert doc.hotel_id and doc.destination_id is None
        else:
            assert doc.destination_id and doc.hotel_id is None


def write_doc(tmp_path, text):
    target = tmp_path / "hotels" / "hotel-xxx-99" / "general.md"
    target.parent.mkdir(parents=True)
    target.write_text(text, encoding="utf-8")
    return tmp_path


def test_unknown_frontmatter_key_is_rejected(tmp_path):
    write_doc(
        tmp_path,
        "---\ndoc_id: x\ncategory: general\ntitle: t\nhotel_id: hotel-xxx-99\n"
        "notes: extra\n---\n\n## Section\n\nBody text.\n",
    )

    with pytest.raises(RagError, match="notes"):
        load_corpus(tmp_path)


def test_missing_title_is_rejected(tmp_path):
    write_doc(tmp_path, "---\ndoc_id: x\ncategory: general\nhotel_id: hotel-xxx-99\n---\n\n## Section\n\nBody.\n")

    with pytest.raises(RagError, match="title"):
        load_corpus(tmp_path)


def test_category_mismatching_filename_is_rejected(tmp_path):
    write_doc(
        tmp_path,
        "---\ndoc_id: x\ncategory: cancellation\ntitle: t\nhotel_id: hotel-xxx-99\n---\n\n## Terms\n\nBody.\n",
    )

    with pytest.raises(RagError, match="category"):
        load_corpus(tmp_path)


def test_duplicate_doc_ids_across_files_are_rejected(tmp_path):
    write_doc(
        tmp_path,
        "---\ndoc_id: same-id\ncategory: general\ntitle: t\nhotel_id: hotel-xxx-99\n---\n\n## Section\n\nBody.\n",
    )
    second = tmp_path / "hotels" / "hotel-xxx-99" / "rooms.md"
    second.write_text(
        "---\ndoc_id: same-id\ncategory: rooms\ntitle: t\nhotel_id: hotel-xxx-99\n---\n\n## Section\n\nBody.\n",
        encoding="utf-8",
    )

    with pytest.raises(RagError, match="same-id"):
        load_corpus(tmp_path)


def test_destination_doc_with_hotel_id_is_rejected(tmp_path):
    target = tmp_path / "destinations" / "lisbon-pt" / "check-in-check-out.md"
    target.parent.mkdir(parents=True)
    target.write_text(
        "---\ndoc_id: x\ncategory: check_in_check_out\ntitle: t\nhotel_id: hotel-lis-01\n---\n\n## Section\n\nBody.\n",
        encoding="utf-8",
    )

    with pytest.raises(RagError):
        load_corpus(tmp_path)
