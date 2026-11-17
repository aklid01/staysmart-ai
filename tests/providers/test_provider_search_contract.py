from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from query import CHECK_IN, CHECK_OUT, make_query

from staysmart.domain.errors import (
    CurrencyMismatchError,
    InvalidDateError,
    UnknownDestinationError,
)
from staysmart.domain.models import Amenity


async def test_search_kyoto_applies_filters_and_reports_partial_availability(provider):
    result = await provider.search(
        make_query(
            destination="Kyoto",
            max_nightly_budget=250.0,
            min_rating=8.0,
            amenities=[Amenity.WIFI, Amenity.BREAKFAST],
            preferences=["quiet room"],
        )
    )

    assert result.total_found == 1
    assert result.data_source == "mock"
    assert result.is_live is False
    assert "preference_not_verified:quiet room" in result.unmet_preferences

    hit = result.results[0]
    assert hit.hotel.hotel_id == "hotel-kyo-01"
    assert hit.quote.room_type_id == "room-kyo-01-std"
    assert hit.matched_amenities == ["BREAKFAST", "WIFI"]
    assert hit.quote.nightly_rates == [252.75, 215.82]
    assert hit.quote.avg_nightly_rate == 234.28
    assert hit.quote.total_price is None
    assert hit.quote.nights == 3
    assert hit.quote.nights_available == 2
    assert hit.quote.available is False
    assert hit.quote.partially_available is True
    assert hit.quote.sold_out_dates == [date(2026, 12, 5)]
    assert hit.hotel.cancellation_policy.policy_type == "partial"


async def test_search_lisbon_sorts_available_before_partial(provider):
    result = await provider.search(
        make_query(
            destination="Lisbon",
            max_nightly_budget=160.0,
            min_rating=7.0,
            amenities=[Amenity.WIFI],
        )
    )

    assert [hit.hotel.hotel_id for hit in result.results] == ["hotel-lis-01", "hotel-lis-02"]
    assert result.total_found == 2
    assert result.unmet_preferences == []

    first = result.results[0]
    assert first.quote.room_type_id == "room-lis-01-std"
    assert first.quote.nightly_rates == [153.32, 154.84, 149.16]
    assert first.quote.avg_nightly_rate == 152.44
    assert first.quote.total_price == 457.32
    assert first.quote.available is True

    second = result.results[1]
    assert second.quote.room_type_id == "room-lis-02-std"
    assert second.quote.nightly_rates == [128.35, 85.17]
    assert second.quote.total_price is None
    assert second.quote.partially_available is True
    assert second.quote.sold_out_dates == [date(2026, 12, 5)]


async def test_search_matches_destination_aliases(provider):
    by_city = await provider.search(make_query(destination="Kyoto"))
    by_region = await provider.search(make_query(destination="Asia"))
    assert by_city.total_found == 3
    assert by_region.total_found == 3
    assert {hit.hotel.hotel_id for hit in by_city.results} == {
        "hotel-kyo-01",
        "hotel-kyo-02",
        "hotel-kyo-03",
    }


async def test_search_empty_result_reports_unmet_filters(provider):
    result = await provider.search(make_query(destination="Lisbon", max_nightly_budget=10.0))

    assert result.total_found == 0
    assert result.results == []
    assert "no_hotels_matched:Lisbon" in result.unmet_preferences
    assert "filter:max_nightly_budget=10.0" in result.unmet_preferences


async def test_search_rejects_unknown_destination(provider):
    with pytest.raises(UnknownDestinationError):
        await provider.search(make_query(destination="Atlantis"))


async def test_search_rejects_out_of_window_dates(provider):
    with pytest.raises(InvalidDateError):
        await provider.search(make_query(check_in=date(2028, 1, 1), check_out=date(2028, 1, 4)))


async def test_search_rejects_currency_mismatch(provider):
    with pytest.raises(CurrencyMismatchError):
        await provider.search(make_query(currency="EUR"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"check_out": CHECK_IN},
        {"guests": 0},
        {"rooms": 0},
        {"max_nightly_budget": 0},
        {"min_rating": 11},
        {"amenities": ["GOLF"]},
        {"check_out": CHECK_IN + timedelta(days=31)},
    ],
)
def test_invalid_query_parameters_are_rejected(overrides):
    with pytest.raises(ValidationError):
        make_query(**overrides)


async def test_mock_markers_are_present_on_every_returned_object(provider):
    search = await provider.search(make_query(destination="Lisbon"))
    details = await provider.get_hotel_details("hotel-lis-01")
    availability = await provider.check_availability("hotel-lis-01", "room-lis-01-std", CHECK_IN, CHECK_OUT)

    objects = [
        search,
        *search.results,
        *[hit.hotel for hit in search.results],
        *[hit.quote for hit in search.results],
        details,
        details.hotel,
        *details.room_quotes,
        availability,
    ]
    assert len(objects) >= 10
    for obj in objects:
        assert obj.data_source == "mock"
        assert obj.is_live is False
