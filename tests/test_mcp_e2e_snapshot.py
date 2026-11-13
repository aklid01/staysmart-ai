import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "golden" / "mcp_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "mcp_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_mcp.py"


def test_e2e_snapshot_matches_spec_authored_golden():
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
    assert data["server_name"] == "staysmart-hotels"
    assert data["transport"] == "in-process"
    assert data["data_source"] == "mock"
    assert data["is_live"] is False
    assert data["tools_listed"] == [
        "check_availability",
        "compare_hotels",
        "get_hotel_details",
        "get_hotel_policies",
        "search_hotels",
    ]

    results = data["results"]
    assert results["search_kyoto_family"]["total_found"] == 1
    assert results["search_kyoto_family"]["hits"][0]["sold_out_dates"] == ["2026-12-05"]
    assert results["search_lisbon_budget"]["hotel_ids"] == ["hotel-lis-01", "hotel-lis-02"]

    comparison = results["compare_lisbon"]
    assert comparison["unresolved_hotel_ids"] == ["hotel-xxx-99"]
    assert comparison["unmet_preferences"] == ["preference_not_verified:river view"]
    assert [row["hotel_id"] for row in comparison["rows"]] == ["hotel-lis-01", "hotel-lis-02"]
    assert comparison["rows"][0]["nightly_price"] == 152.44
    assert comparison["rows"][0]["total_stay_price"] == 457.32
    assert comparison["rows"][1]["total_stay_price"] is None
    assert comparison["rows"][1]["availability"] is False

    policies_kyo = results["policies_kyo_01"]
    assert policies_kyo["pet_policy"] == "allowed"
    assert policies_kyo["pet_policy_source"] == "amenities"
    assert policies_kyo["information_gaps"] == ["check_in_time", "check_out_time"]

    policies_lis = results["policies_lis_01"]
    assert policies_lis["pet_policy"] == "unknown"
    assert policies_lis["pet_policy_source"] == "not_provided"
    assert policies_lis["information_gaps"] == ["check_in_time", "check_out_time", "pet_policy"]

    errors = data["errors"]
    for record in errors.values():
        assert record["is_error"] is True
    assert errors["unknown_destination_search"]["message"].endswith(
        "No destination matches 'Atlantis' in the mock dataset"
    )
    assert errors["unknown_hotel_details"]["message"].endswith("Unknown hotel_id 'hotel-xxx-99' in the mock dataset")
    assert errors["invalid_dates_availability"]["message"].endswith(
        "Stay must be between 1 and 30 nights, got -3 from 2026-12-07 to 2026-12-04"
    )
