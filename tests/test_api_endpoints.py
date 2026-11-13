import contextlib

from starlette.testclient import TestClient

from staysmart.agent.errors import LLMUnavailableError
from staysmart.agent.llm import ScriptedLLM
from staysmart.app.main import create_app
from staysmart.app.mcp_client import InProcessMcpConnector
from staysmart.domain.models import (
    AvailabilityResult,
    HotelComparison,
    HotelDetails,
    HotelPolicyInfo,
    HotelSearchResult,
)
from staysmart.mcp_server.server import build_mcp_server

STAY_DATES = {"check_in": "2026-12-04", "check_out": "2026-12-07"}

KYOTO_SEARCH_BODY = {
    "destination": "Kyoto",
    **STAY_DATES,
    "guests": 2,
    "rooms": 1,
    "max_nightly_budget": 250.0,
    "min_rating": 8.0,
    "amenities": ["WIFI", "BREAKFAST"],
    "preferences": ["quiet room"],
}

LISBON_SEARCH_BODY = {
    "destination": "Lisbon",
    **STAY_DATES,
    "max_nightly_budget": 160.0,
    "min_rating": 7.0,
    "amenities": ["WIFI"],
}

COMPARE_BODY = {
    "hotel_ids": ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"],
    **STAY_DATES,
    "rooms": 1,
    "guests": 2,
    "preferences": ["river view"],
}


class ExplodingProvider:
    async def search(self, query):
        raise RuntimeError("boom")

    async def get_hotel_details(self, hotel_id, **kwargs):
        raise RuntimeError("boom")

    async def check_availability(self, hotel_id, room_type_id, check_in, check_out, rooms=1):
        raise RuntimeError("boom")


class FailingSession:
    async def list_tools(self):
        raise RuntimeError("session lost")

    async def call_tool(self, name, arguments):
        raise RuntimeError("session lost")


class FailingConnector:
    def connect(self):
        @contextlib.asynccontextmanager
        async def session():
            yield FailingSession()

        return session()


def test_search_kyoto_family_returns_mock_marked_results(client):
    response = client.post("/api/search", json=KYOTO_SEARCH_BODY)

    assert response.status_code == 200
    body = response.json()
    model = HotelSearchResult.model_validate(body)
    assert model.data_source == "mock"
    assert model.is_live is False
    assert body["total_found"] == 1
    hit = body["results"][0]
    assert hit["hotel"]["hotel_id"] == "hotel-kyo-01"
    assert hit["quote"]["avg_nightly_rate"] == 234.28
    assert hit["quote"]["total_price"] is None
    assert hit["quote"]["sold_out_dates"] == ["2026-12-05"]
    assert body["unmet_preferences"] == ["preference_not_verified:quiet room"]


def test_search_lisbon_budget_returns_pinned_hits(client):
    response = client.post("/api/search", json=LISBON_SEARCH_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["total_found"] == 2
    assert [hit["hotel"]["hotel_id"] for hit in body["results"]] == ["hotel-lis-01", "hotel-lis-02"]
    assert body["results"][0]["quote"]["total_price"] == 457.32
    assert body["results"][1]["quote"]["total_price"] is None
    assert body["results"][1]["quote"]["sold_out_dates"] == ["2026-12-05"]


def test_unknown_destination_maps_to_404(client):
    response = client.post("/api/search", json={"destination": "Atlantis", **STAY_DATES})

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "unknown_destination"
    assert error["error_type"] == "UnknownDestinationError"
    assert error["message"] == "No destination matches 'Atlantis' in the mock dataset"


def test_reversed_search_dates_map_to_400(client):
    response = client.post(
        "/api/search", json={"destination": "Kyoto", "check_in": "2026-12-07", "check_out": "2026-12-04"}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_date"
    assert error["error_type"] == "InvalidDateError"
    assert error["message"] == "check_out must be after check_in"


def test_stay_beyond_30_nights_maps_to_400(client):
    response = client.post(
        "/api/search",
        json={"destination": "Kyoto", "check_in": "2026-12-04", "check_out": "2027-02-10"},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_date"
    assert error["message"] == "stay length must be between 1 and 30 nights"


def test_missing_destination_returns_validation_error(client):
    response = client.post("/api/search", json=STAY_DATES)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["error_type"] == "ValidationError"
    assert error["message"] == "Request validation failed"
    assert error["details"] == [{"loc": ["destination"], "msg": "Field required", "type": "missing"}]


def test_unknown_amenity_returns_validation_error(client):
    response = client.post(
        "/api/search",
        json={"destination": "Kyoto", **STAY_DATES, "amenities": ["WIFI", "JACUZZI"]},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["type"] == "enum"
    assert error["details"][0]["loc"][0] == "amenities"


def test_non_positive_rooms_returns_validation_error(client):
    response = client.post("/api/search", json={"destination": "Kyoto", **STAY_DATES, "rooms": 0})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["details"][0]["type"] == "greater_than_equal"
    assert error["details"][0]["loc"] == ["rooms"]


def test_malformed_json_body_returns_invalid_json(client):
    response = client.post("/api/search", content=b"{not json", headers={"content-type": "application/json"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_json"
    assert error["error_type"] == "InvalidJsonError"
    assert error["message"] == "Request body is not valid JSON"


def test_unknown_route_returns_not_found(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["error_type"] == "NotFoundError"


def test_exploding_provider_maps_to_generic_tool_error(settings):
    exploding = ExplodingProvider()
    app = create_app(settings, connector=InProcessMcpConnector(build_mcp_server(settings, exploding)))
    with TestClient(app) as client:
        response = client.post("/api/search", json=KYOTO_SEARCH_BODY)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "tool_error"
    assert error["error_type"] == "ToolError"
    assert error["message"] == "Error executing tool search_hotels"


def test_session_failure_maps_to_unavailable(settings):
    app = create_app(settings, connector=FailingConnector())
    with TestClient(app) as client:
        response = client.post("/api/search", json=KYOTO_SEARCH_BODY)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "mcp_unavailable"
    assert error["error_type"] == "McpUnavailableError"
    assert error["message"] == "RuntimeError while calling tool search_hotels"


def test_details_with_dates_return_pinned_quotes(client):
    response = client.get(
        "/api/hotels/hotel-lis-01",
        params={"check_in": "2026-12-04", "check_out": "2026-12-07", "rooms": 1, "guests": 2},
    )

    assert response.status_code == 200
    body = response.json()
    model = HotelDetails.model_validate(body)
    assert model.data_source == "mock"
    assert body["hotel"]["hotel_id"] == "hotel-lis-01"
    assert body["room_quotes"][0]["total_price"] == 457.32
    assert body["room_quotes"][1]["total_price"] is None
    assert body["cancellation_policy"]["policy_type"] == "free"
    assert body["cancellation_policy"]["refundable"] is True


def test_details_default_dates_land_on_anchor_single_night(client):
    response = client.get("/api/hotels/hotel-lis-01")

    assert response.status_code == 200
    body = response.json()
    assert body["check_in"] == "2026-11-01"
    assert body["check_out"] == "2026-11-02"


def test_unknown_hotel_maps_to_404(client):
    response = client.get("/api/hotels/hotel-xxx-99")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "unknown_hotel"
    assert error["error_type"] == "UnknownHotelError"
    assert error["message"] == "Unknown hotel_id 'hotel-xxx-99' in the mock dataset"


def test_invalid_details_query_params_return_422(client):
    response = client.get("/api/hotels/hotel-lis-01", params={"rooms": 0})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["rooms"]

    response = client.get("/api/hotels/hotel-lis-01", params={"check_in": "not-a-date"})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["check_in"]


def test_availability_sold_out_stay_is_success(client):
    response = client.post(
        "/api/hotels/hotel-van-03/availability",
        json={"room_type_id": "room-van-03-std", **STAY_DATES, "rooms": 1},
    )

    assert response.status_code == 200
    body = response.json()
    model = AvailabilityResult.model_validate(body)
    assert model.data_source == "mock"
    assert body["available"] is False
    assert body["nights_requested"] == 3
    assert body["nights_available"] == 0
    assert body["sold_out_dates"] == ["2026-12-04", "2026-12-05", "2026-12-06"]
    assert body["nightly_rates"] == []
    assert body["total_price"] is None


def test_unknown_room_type_maps_to_404(client):
    response = client.post(
        "/api/hotels/hotel-lis-02/availability",
        json={"room_type_id": "room-lis-02-suite", **STAY_DATES},
    )

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "unknown_room_type"
    assert error["error_type"] == "UnknownRoomTypeError"
    assert error["message"] == "Unknown room_type_id 'room-lis-02-suite' for hotel 'hotel-lis-02'"


def test_reversed_availability_dates_map_to_400(client):
    response = client.post(
        "/api/hotels/hotel-lis-02/availability",
        json={"room_type_id": "room-lis-02-std", "check_in": "2026-12-07", "check_out": "2026-12-04"},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_date"
    assert error["message"] == "Stay must be between 1 and 30 nights, got -3 from 2026-12-07 to 2026-12-04"


def test_compare_reports_rows_and_unresolved_ids(client):
    response = client.post("/api/compare", json=COMPARE_BODY)

    assert response.status_code == 200
    body = response.json()
    model = HotelComparison.model_validate(body)
    assert model.data_source == "mock"
    assert [row["hotel_id"] for row in body["rows"]] == ["hotel-lis-01", "hotel-lis-02"]
    assert body["unresolved_hotel_ids"] == ["hotel-xxx-99"]
    assert body["unmet_preferences"] == ["preference_not_verified:river view"]
    assert body["rows"][0]["nightly_price"] == 152.44
    assert body["rows"][0]["total_stay_price"] == 457.32
    assert body["rows"][0]["availability"] is True
    assert body["rows"][1]["nightly_price"] == 106.76
    assert body["rows"][1]["total_stay_price"] is None
    assert body["rows"][1]["availability"] is False


def test_empty_hotel_ids_map_to_400(client):
    response = client.post("/api/compare", json={"hotel_ids": [], **STAY_DATES})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "empty_hotel_ids"
    assert error["error_type"] == "ToolError"
    assert error["message"] == "hotel_ids must contain at least one hotel id"


def test_policies_for_pet_friendly_hotel(client):
    response = client.get("/api/hotels/hotel-kyo-01/policies")

    assert response.status_code == 200
    body = response.json()
    model = HotelPolicyInfo.model_validate(body)
    assert model.data_source == "mock"
    assert body["pet_policy"] == "allowed"
    assert body["pet_policy_source"] == "amenities"
    assert body["cancellation_policy"]["policy_type"] == "partial"
    assert body["cancellation_policy"]["free_cancellation_days"] == 5
    assert body["cancellation_policy"]["penalty_nights"] == 1
    assert body["information_gaps"] == ["check_in_time", "check_out_time"]
    assert body["check_in_time"] is None


def test_policies_for_non_pet_hotel_report_gaps(client):
    response = client.get("/api/hotels/hotel-lis-01/policies")

    assert response.status_code == 200
    body = response.json()
    assert body["pet_policy"] == "unknown"
    assert body["pet_policy_source"] == "not_provided"
    assert body["information_gaps"] == ["check_in_time", "check_out_time", "pet_policy"]


def test_chat_maps_unavailable_llm_to_503(settings, mcp_server, retriever):
    app = create_app(
        settings,
        connector=InProcessMcpConnector(mcp_server),
        llm=ScriptedLLM([LLMUnavailableError("connection refused")]),
        retriever=retriever,
    )
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "Find a hotel in Kyoto"})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "llm_unavailable"
    assert error["error_type"] == "LLMUnavailableError"


def test_chat_empty_message_returns_validation_error(client):
    response = client.post("/api/chat", json={"message": ""})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["message"]
    assert error["details"][0]["type"] == "string_too_short"


def test_chat_rejects_invalid_history_role(client):
    response = client.post(
        "/api/chat",
        json={"message": "hello", "history": [{"role": "system", "content": "nope"}]},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["details"][0]["type"] == "literal_error"


def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        "/api/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_rejects_unknown_origin(client):
    response = client.options(
        "/api/search",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
