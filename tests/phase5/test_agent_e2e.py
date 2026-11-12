import json
import socket
import subprocess
import sys
from urllib.parse import urlparse

import pytest


def _endpoint_reachable() -> bool:
    from staysmart.config import Settings

    settings = Settings.from_env(env={})
    parsed = urlparse(settings.llm_base_url)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _endpoint_reachable(), reason="LLM endpoint not reachable")
def test_agent_e2e_artifact_records_real_model_run(demo_script, artifact_path):
    completed = subprocess.run(
        [sys.executable, str(demo_script)],
        cwd=str(demo_script.parent.parent),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    data = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert data["artifact_version"] == 1
    assert data["model"]
    assert data["data_source"] == "mock"

    scenarios = data["scenarios"]
    search = scenarios["search_kyoto"]
    assert "search_hotels" in [entry["tool"] for entry in search["tool_trace"]]
    assert search["hotel_ids"]
    assert search["message"]

    policy = scenarios["policy_kyoto"]
    assert policy["sources"]
    assert any("check" in source["category"] or source["category"] == "pet_policy" for source in policy["sources"])

    comparison = scenarios["compare_lisbon"]
    assert comparison["comparison"] is not None
    assert comparison["comparison"]["rows"]
    assert comparison["message"]

    for scenario in scenarios.values():
        for hotel_id in scenario["hotel_ids"]:
            assert hotel_id.startswith("hotel-")
