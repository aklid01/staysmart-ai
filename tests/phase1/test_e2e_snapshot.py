import json
import subprocess
import sys


def test_e2e_snapshot_matches_spec_authored_golden(golden_path, artifact_path, demo_script):
    completed = subprocess.run(
        [sys.executable, str(demo_script)],
        cwd=str(demo_script.parent.parent),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    artifact = artifact_path.read_bytes().replace(b"\r\n", b"\n")
    golden = golden_path.read_bytes().replace(b"\r\n", b"\n")
    assert artifact == golden

    data = json.loads(artifact)
    assert data["artifact_version"] == 1
    assert data["data_source"] == "mock"
    assert data["is_live"] is False
    assert data["currency"] == "USD"
    assert data["dataset_schema_version"] == 1

    kyoto = data["searches"]["kyoto_family"]
    assert kyoto["total_found"] == 1
    assert kyoto["hotel_ids"] == ["hotel-kyo-01"]
    assert kyoto["unmet_preferences"] == ["preference_not_verified:quiet room"]
    assert kyoto["hits"][0]["available"] is False
    assert kyoto["hits"][0]["partially_available"] is True
    assert kyoto["hits"][0]["sold_out_dates"] == ["2026-12-05"]
    assert kyoto["hits"][0]["total_price"] is None
    assert kyoto["hits"][0]["matched_amenities"] == ["BREAKFAST", "WIFI"]
    assert kyoto["hits"][0]["cancellation_policy"] == "partial"

    lisbon = data["searches"]["lisbon_budget"]
    assert lisbon["hotel_ids"] == ["hotel-lis-01", "hotel-lis-02"]
    assert lisbon["hits"][0]["total_price"] == 457.32
    assert lisbon["hits"][0]["available"] is True
    assert lisbon["hits"][1]["total_price"] is None
    assert lisbon["hits"][1]["partially_available"] is True

    details = data["details"]
    assert details["cancellation_policy"] == "free"
    assert details["refundable"] is True
    assert [row["room_type_id"] for row in details["room_quotes"]] == [
        "room-lis-01-std",
        "room-lis-01-suite",
    ]
    assert details["room_quotes"][1]["total_price"] is None

    availability = data["availability"]
    assert availability["nights_requested"] == 3
    assert availability["nights_available"] == 0
    assert availability["available"] is False
    assert availability["total_price"] is None
    assert availability["sold_out_dates"] == [
        "2026-12-04",
        "2026-12-05",
        "2026-12-06",
    ]
