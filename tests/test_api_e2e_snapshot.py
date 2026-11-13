import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "golden" / "api_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "api_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_api.py"


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
    assert data["service"] == "staysmart-api"
    assert data["server_name"] == "staysmart-hotels"
    assert data["transport"] == "stdio"
    assert data["base_url"] == "http://127.0.0.1"
    assert data["data_source"] == "mock"
    assert data["is_live"] is False

    requests = data["requests"]
    assert requests["health"]["status"] == 200
    assert requests["health"]["body"]["mcp_server"]["connected"] is True
    assert requests["health"]["body"]["mcp_server"]["tools"] == [
        "check_availability",
        "compare_hotels",
        "get_hotel_details",
        "get_hotel_policies",
        "search_hotels",
    ]

    assert requests["search_kyoto_family"]["status"] == 200
    assert requests["search_kyoto_family"]["body"]["total_found"] == 1
    assert requests["search_kyoto_family"]["body"]["hits"][0]["sold_out_dates"] == ["2026-12-05"]
    assert requests["search_lisbon_budget"]["body"]["hotel_ids"] == ["hotel-lis-01", "hotel-lis-02"]

    assert requests["details_lis_01"]["status"] == 200
    assert requests["details_lis_01"]["body"]["room_quotes"][0]["total_price"] == 457.32

    assert requests["availability_van_03"]["status"] == 200
    assert requests["availability_van_03"]["body"]["available"] is False
    assert requests["availability_van_03"]["body"]["total_price"] is None

    comparison = requests["compare_lisbon"]["body"]
    assert comparison["unresolved_hotel_ids"] == ["hotel-xxx-99"]
    assert [row["hotel_id"] for row in comparison["rows"]] == ["hotel-lis-01", "hotel-lis-02"]

    assert requests["policies_kyo_01"]["body"]["pet_policy"] == "allowed"
    assert requests["policies_lis_01"]["body"]["pet_policy"] == "unknown"

    assert requests["chat_agent"]["status"] == 200
    assert requests["chat_agent"]["body"]["message"].startswith("This API demo records a scripted model reply")
    assert requests["chat_agent"]["body"]["conversation_id"] == "demo-conversation"
    assert requests["chat_agent"]["body"]["tool_trace"] == []

    errors = data["errors"]
    assert errors["unknown_destination_search"]["status"] == 404
    assert errors["unknown_hotel_details"]["status"] == 404
    assert errors["invalid_dates_availability"]["status"] == 400
    assert errors["empty_compare_hotel_ids"]["status"] == 400
    assert errors["validation_missing_destination"]["status"] == 422
    assert errors["chat_empty_message"]["status"] == 422
    assert errors["unknown_destination_search"]["body"]["error"]["message"].endswith(
        "No destination matches 'Atlantis' in the mock dataset"
    )
    assert errors["invalid_dates_availability"]["body"]["error"]["message"].endswith(
        "Stay must be between 1 and 30 nights, got -3 from 2026-12-07 to 2026-12-04"
    )
