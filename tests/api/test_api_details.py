from staysmart.domain.models import (
    HotelDetails,
    HotelPolicyInfo,
)


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
