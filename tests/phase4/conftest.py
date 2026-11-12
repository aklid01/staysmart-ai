from pathlib import Path

import pytest

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.providers.mock.dataset import load_dataset
from staysmart.rag.embedder import DeterministicEmbedder
from staysmart.rag.ingest import build_index
from staysmart.rag.service import RagRetriever

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data" / "knowledge" / "v1"
DATASET_PATH = ROOT / "data" / "hotels" / "v1" / "hotels.json"
GOLDEN_PATH = ROOT / "tests" / "phase4" / "golden" / "rag_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "rag_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_rag.py"


@pytest.fixture
def settings():
    return Settings(
        hotel_provider="mock",
        dataset_path=DATASET_PATH,
        log_level="WARNING",
        currency="USD",
        window_days=365,
        http_host="127.0.0.1",
        http_port=8000,
        cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
        rag_corpus_path=CORPUS_PATH,
        rag_index_path=PROJECT_ROOT / "data" / "rag" / "index",
        rag_model="BAAI/bge-small-en-v1.5",
    )


@pytest.fixture
def corpus_path():
    return CORPUS_PATH


@pytest.fixture
def dataset_path():
    return DATASET_PATH


@pytest.fixture
def stub_index(tmp_path):
    dataset = load_dataset(DATASET_PATH)
    destination_by_hotel = {hotel.hotel_id: hotel.destination_id for hotel in dataset.hotels}
    return build_index(CORPUS_PATH, tmp_path / "index", DeterministicEmbedder(), destination_by_hotel)


@pytest.fixture
def retriever(stub_index):
    return RagRetriever(stub_index, DeterministicEmbedder())


@pytest.fixture
def golden_path():
    return GOLDEN_PATH


@pytest.fixture
def artifact_path():
    return ARTIFACT_PATH


@pytest.fixture
def demo_script():
    return DEMO_SCRIPT
