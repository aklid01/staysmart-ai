import json
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

from staysmart.config import Settings


def _root():
    return Path(__file__).resolve().parents[2]


ARTIFACT_SPECS = [
    ("scripts/demo_provider.py", "artifacts/provider_demo.json"),
    ("scripts/demo_mcp.py", "artifacts/mcp_demo.json"),
    ("scripts/demo_api.py", "artifacts/api_demo.json"),
]

RETRIEVAL_ARTIFACT = ("scripts/demo_rag.py", "artifacts/rag_demo.json")


@pytest.mark.parametrize("demo_script,artifact", ARTIFACT_SPECS)
def test_demo_script_regenerates_mock_marked_artifact(demo_script, artifact):
    root = _root()
    completed = subprocess.run(
        [sys.executable, str(root / demo_script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr

    data = json.loads((root / artifact).read_text(encoding="utf-8"))
    assert data["artifact_version"] == 1
    assert data["data_source"] == "mock"
    assert data["is_live"] is False


def test_demo_script_regenerates_retrieval_artifact():
    root = _root()
    demo_script, artifact = RETRIEVAL_ARTIFACT
    completed = subprocess.run(
        [sys.executable, str(root / demo_script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr

    data = json.loads((root / artifact).read_text(encoding="utf-8"))
    assert data["artifact_version"] == 1
    assert data["doc_count"] == 53
    assert data["chunk_count"] > 0


def test_agent_demo_artifact_when_llm_reachable():
    root = _root()
    settings = Settings.from_env(env={})
    parsed = urlparse(settings.llm_base_url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=2):
            reachable = True
    except OSError:
        reachable = False

    if not reachable:
        pytest.skip("LLM endpoint not reachable")

    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "demo_agent.py")],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stderr

    data = json.loads((root / "artifacts" / "agent_demo.json").read_text(encoding="utf-8"))
    assert data["artifact_version"] == 1
    assert data["data_source"] == "mock"
    dataset = json.loads((root / "data" / "hotels" / "v1" / "hotels.json").read_text(encoding="utf-8"))
    dataset_ids = {hotel["hotel_id"] for hotel in dataset["hotels"]}
    for scenario in data["scenarios"].values():
        for hotel_id in scenario["hotel_ids"]:
            assert hotel_id in dataset_ids, f"fabricated hotel id {hotel_id}"
        assert scenario["message"]
