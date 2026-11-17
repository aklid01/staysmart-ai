import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "tests" / "golden" / "rag_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "rag_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_rag.py"


def test_rag_snapshot_matches_generated_golden():
    completed = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    artifact = ARTIFACT_PATH.read_bytes().replace(b"\r\n", b"\n")
    golden = GOLDEN_PATH.read_bytes().replace(b"\r\n", b"\n")
    assert artifact == golden

    data = json.loads(artifact)
    assert data["artifact_version"] == 1
    assert data["model"] == "BAAI/bge-small-en-v1.5"
    assert data["embedding_dim"] == 384
    assert data["doc_count"] == 53
    assert data["chunk_count"] > 0

    queries = data["queries"]
    assert queries["pet_policy_kyoto"]["results"][0]["doc_id"] == "hotel-kyo-01-pet-policy"
    assert queries["cancellation_lisbon"]["results"][0]["doc_id"] == "hotel-lis-01-cancellation"
    assert queries["check_in_kyoto"]["results"][0]["doc_id"] == "kyoto-jp-check-in-check-out"
    assert queries["parking_lisbon"]["results"][0]["doc_id"] == "hotel-lis-02-amenities"

    for key in ["quiet_breakfast_room", "spa_vancouver"]:
        results = queries[key]["results"]
        assert len(results) == 4
        scores = [result["score"] for result in results]
        assert scores == sorted(scores, reverse=True)
        for result in results:
            assert result["score"] == round(result["score"], 4)
            assert result["category"]
            assert result["text"]

    pet_results = queries["pet_policy_kyoto"]["results"]
    assert all(result["hotel_id"] == "hotel-kyo-01" for result in pet_results)

    for scenario in queries.values():
        assert scenario["sources"]
        for source in scenario["sources"]:
            assert source["chunk_count"] >= 1
