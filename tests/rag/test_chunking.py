from staysmart.rag.chunking import MAX_CHUNK_CHARS, chunk_document
from staysmart.rag.corpus import KnowledgeDocument


def make_doc(body: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        doc_id="doc-1",
        category="general",
        title="Sample hotel overview",
        hotel_id="hotel-xxx-99",
        destination_id=None,
        source_path="hotels/hotel-xxx-99/general.md",
        body=body,
    )


def test_overview_text_before_first_heading_becomes_its_own_chunk():
    doc = make_doc("Intro paragraph about the house.\n\n## Rooms\n\nRoom body text.\n")

    chunks = chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].heading == "Sample hotel overview"
    assert chunks[0].text == "Intro paragraph about the house."
    assert chunks[1].heading == "Rooms"
    assert chunks[1].text == "Room body text."


def test_chunk_metadata_and_ids_are_sequential_per_document():
    doc = make_doc("Intro.\n\n## One\n\nFirst body.\n\n## Two\n\nSecond body.\n")

    chunks = chunk_document(doc)

    assert [chunk.chunk_id for chunk in chunks] == ["doc-1:0", "doc-1:1", "doc-1:2"]
    for chunk in chunks:
        assert chunk.doc_id == "doc-1"
        assert chunk.title == "Sample hotel overview"
        assert chunk.category == "general"
        assert chunk.hotel_id == "hotel-xxx-99"
        assert chunk.destination_id is None
        assert chunk.source_path == "hotels/hotel-xxx-99/general.md"


def test_long_section_splits_on_paragraph_boundaries_under_the_limit():
    paragraph_a = "A" * 400
    paragraph_b = "B" * 400
    doc = make_doc(f"## Section\n\n{paragraph_a}\n\n{paragraph_b}\n")

    chunks = chunk_document(doc)

    assert len(chunks) == 2
    assert all(len(chunk.text) <= MAX_CHUNK_CHARS for chunk in chunks)
    assert chunks[0].text == paragraph_a
    assert chunks[1].text == paragraph_b


def test_single_paragraph_over_the_limit_stays_one_chunk():
    paragraph = "C" * 900
    doc = make_doc(f"## Section\n\n{paragraph}\n")

    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].text == paragraph


def test_embedded_text_composes_title_heading_and_text():
    doc = make_doc("Intro text.\n\n## Amenities\n\nFacility text.\n")

    chunks = chunk_document(doc)

    assert chunks[0].embedded_text() == "Sample hotel overview - Sample hotel overview\nIntro text."
    assert chunks[1].embedded_text() == "Sample hotel overview - Amenities\nFacility text."


def test_real_corpus_chunks_respect_the_limit(corpus_path):
    from staysmart.rag.corpus import load_corpus

    for doc in load_corpus(corpus_path):
        for chunk in chunk_document(doc):
            assert len(chunk.text) <= MAX_CHUNK_CHARS
            assert chunk.text.strip() == chunk.text
