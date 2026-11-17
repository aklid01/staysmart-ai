from bodies import COMPARE_BODY, STAY_DATES

from staysmart.domain.models import (
    AvailabilityResult,
    HotelComparison,
)


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
    assert error["message"] == "check_out must be after check_in"


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
    assert error["code"] == "invalid_argument"
    assert error["error_type"] == "InvalidArgumentError"
    assert error["message"] == "hotel_ids must contain at least one hotel id"
