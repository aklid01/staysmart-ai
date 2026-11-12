import json
from pathlib import Path

from staysmart.agent.llm import LLMCompletion, LLMToolCall
from staysmart.providers.mock.dataset import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "hotels" / "v1" / "hotels.json"

STAY = {"check_in": "2026-12-04", "check_out": "2026-12-07"}


def test_full_journey_across_every_layer(full_client):
    client, llm = full_client
    llm.steps.extend(
        [
            LLMCompletion(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="call-1",
                        name="search_hotels",
                        arguments={"destination": "Kyoto", **STAY, "guests": 2, "rooms": 1},
                    )
                ],
            ),
            LLMCompletion(
                content=None,
                tool_calls=[
                    LLMToolCall(
                        id="call-2",
                        name="search_knowledge",
                        arguments={
                            "query": "check-in and check-out requirements in Kyoto",
                            "destination_id": "kyoto-jp",
                        },
                    )
                ],
            ),
            LLMCompletion(
                content="Kyoto options are listed below. Check-in starts at 15:00 per the Kyoto guide.",
                tool_calls=[],
            ),
        ]
    )

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mcp_server"]["connected"] is True

    chat = client.post(
        "/api/chat",
        json={"message": "Hotels in Kyoto for two guests in December", "conversation_id": "journey"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["conversation_id"] == "journey"
    trace = [(entry["tool"], entry["status"]) for entry in body["tool_trace"]]
    assert trace == [("search_hotels", "ok"), ("search_knowledge", "ok")]
    assert body["sources"], "knowledge citations must accompany the knowledge call"

    dataset = load_dataset(DATASET_PATH)
    dataset_ids = {hotel.hotel_id for hotel in dataset.hotels}
    card_ids = {entry["hotel"]["hotel_id"] for entry in body["hotels"]}
    assert card_ids and card_ids <= dataset_ids
    assert all(
        entry["hotel"]["data_source"] == "mock" and entry["hotel"]["is_live"] is False
        for entry in body["hotels"]
    )
    assert any(source["category"] == "check_in_check_out" for source in body["sources"])

    search = client.post(
        "/api/search",
        json={
            "destination": "Kyoto",
            **STAY,
            "max_nightly_budget": 250.0,
            "min_rating": 8.0,
            "amenities": ["WIFI", "BREAKFAST"],
        },
    )
    assert search.status_code == 200
    assert search.json()["total_found"] == 1

    details = client.get("/api/hotels/hotel-kyo-01", params=STAY)
    assert details.status_code == 200
    assert details.json()["hotel"]["hotel_id"] == "hotel-kyo-01"

    policies = client.get("/api/hotels/hotel-kyo-01/policies")
    assert policies.status_code == 200
    assert policies.json()["information_gaps"] == ["check_in_time", "check_out_time"]

    compare = client.post(
        "/api/compare",
        json={"hotel_ids": ["hotel-lis-01", "hotel-lis-02"], **STAY, "rooms": 1, "guests": 2},
    )
    assert compare.status_code == 200
    comparison = compare.json()
    assert [row["hotel_id"] for row in comparison["rows"]] == ["hotel-lis-01", "hotel-lis-02"]
    assert comparison["data_source"] == "mock"
