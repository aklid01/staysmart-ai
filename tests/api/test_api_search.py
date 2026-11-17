from bodies import KYOTO_SEARCH_BODY, LISBON_SEARCH_BODY, STAY_DATES

from staysmart.domain.models import (
    HotelSearchResult,
)


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
