"""Project-specific RAG index composition: mock dataset destination map plus corpus."""

from staysmart.config import Settings
from staysmart.providers.mock.dataset import load_dataset
from staysmart.rag.embedder import Embedder, FastEmbedEmbedder
from staysmart.rag.index import VectorIndex
from staysmart.rag.ingest import build_index


def build_project_index(settings: Settings, embedder: Embedder | None = None) -> tuple[VectorIndex, Embedder]:
    dataset = load_dataset(settings.dataset_path)
    destination_by_hotel = {hotel.hotel_id: hotel.destination_id for hotel in dataset.hotels}
    if embedder is None:
        embedder = FastEmbedEmbedder(settings.rag_model)
    index = build_index(
        settings.rag_corpus_path,
        settings.rag_index_path,
        embedder,
        destination_by_hotel=destination_by_hotel,
    )
    return index, embedder
