from pathlib import Path

import pytest
from starlette.testclient import TestClient

from staysmart.agent.llm import ScriptedLLM
from staysmart.app.main import create_app
from staysmart.app.mcp_client import InProcessMcpConnector
from staysmart.config import Settings
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.provider import MockHotelProvider

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "hotels" / "v1" / "hotels.json"
GOLDEN_PATH = ROOT / "tests" / "phase3" / "golden" / "api_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "api_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_api.py"


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
    )


@pytest.fixture
def provider(settings):
    return MockHotelProvider(settings)


@pytest.fixture
def mcp_server(provider, settings):
    return build_mcp_server(settings, provider)


@pytest.fixture
def app(settings, mcp_server):
    return create_app(
        settings,
        connector=InProcessMcpConnector(mcp_server),
        llm=ScriptedLLM([]),
    )


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def golden_path():
    return GOLDEN_PATH


@pytest.fixture
def artifact_path():
    return ARTIFACT_PATH


@pytest.fixture
def demo_script():
    return DEMO_SCRIPT
