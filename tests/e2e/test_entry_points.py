import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SMOKE_PORT = 8973


def test_app_entry_point_serves_health():
    env = {**os.environ, "STAYSMART_HTTP_PORT": str(SMOKE_PORT), "STAYSMART_LOG_LEVEL": "WARNING"}
    process = subprocess.Popen(
        [sys.executable, "-m", "staysmart.app"],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        url = f"http://127.0.0.1:{SMOKE_PORT}/api/health"
        deadline = time.monotonic() + 60
        payload = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"server exited early: {output}")
            try:
                response = httpx.get(url, timeout=2)
                if response.status_code == 200:
                    payload = response.json()
                    break
            except httpx.TransportError:
                time.sleep(0.25)
        assert payload is not None, "health endpoint never became ready"
        assert payload["status"] == "ok"
    finally:
        process.terminate()
        process.wait(timeout=30)


def test_rag_entry_point_ingests_into_tmp_index(tmp_path):
    env = {
        **os.environ,
        "STAYSMART_RAG_INDEX_PATH": str(tmp_path / "index"),
        "STAYSMART_LOG_LEVEL": "WARNING",
    }
    completed = subprocess.run(
        [sys.executable, "-m", "staysmart.rag", "ingest"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ingested" in completed.stdout
    assert (tmp_path / "index" / "manifest.json").exists()
