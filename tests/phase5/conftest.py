from pathlib import Path

import pytest
from starlette.testclient import TestClient

from staysmart.agent.llm import ScriptedLLM
from staysmart.app.main import create_app
from staysmart.app.mcp_client import InProcessMcpConnector
from staysmart.config import Settings
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import MockHotelProvider
from staysmart.rag.embedder import DeterministicEmbedder
from staysmart.rag.ingest import build_index
from staysmart.rag.service import RagRetriever

ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = ROOT / "data" / "knowledge" / "v1"
DATASET_PATH = ROOT / "data" / "hotels" / "v1" / "hotels.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_agent.py"
ARTIFACT_PATH = ROOT / "artifacts" / "agent_demo.json"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        hotel_provider="mock",
        dataset_path=DATASET_PATH,
        log_level="WARNING",
        currency="USD",
        window_days=365,
        http_host="127.0.0.1",
        http_port=8000,
        cors_origins=("http://localhost:5173",),
        rag_corpus_path=CORPUS_PATH,
        rag_index_path=tmp_path / "index",
        rag_model="BAAI/bge-small-en-v1.5",
        llm_base_url="http://127.0.0.1:3425/v1",
        llm_api_key="",
        llm_model="auto/glm-5.3-flash",
    )


@pytest.fixture
def destination_by_hotel():
    dataset = load_dataset(DATASET_PATH)
    return {hotel.hotel_id: hotel.destination_id for hotel in dataset.hotels}


@pytest.fixture
def provider(settings):
    return MockHotelProvider(settings)


@pytest.fixture
def mcp_server(provider, settings):
    return build_mcp_server(settings, provider)


@pytest.fixture
def stub_index(tmp_path, destination_by_hotel):
    return build_index(CORPUS_PATH, tmp_path / "index", DeterministicEmbedder(), destination_by_hotel)


@pytest.fixture
def retriever(stub_index):
    return RagRetriever(stub_index, DeterministicEmbedder())


@pytest.fixture
def agent_llm():
    return ScriptedLLM([])


@pytest.fixture
def app(settings, mcp_server, agent_llm, retriever):
    return create_app(
        settings,
        connector=InProcessMcpConnector(mcp_server),
        llm=agent_llm,
        retriever=retriever,
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def demo_script():
    return DEMO_SCRIPT


@pytest.fixture
def artifact_path():
    return ARTIFACT_PATH
