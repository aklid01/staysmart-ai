import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from staysmart.config import Settings, configure_logging
from staysmart.domain.errors import (
    CurrencyMismatchError,
    InvalidDateError,
    ProviderError,
    UnknownDestinationError,
    UnknownHotelError,
    UnknownRoomTypeError,
)
from staysmart.domain.models import Amenity, HotelSearchQuery
from staysmart.providers.mock.provider import MockHotelProvider, get_provider

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)


def make_query(**overrides):
    values = {
        "destination": "Kyoto",
        "check_in": CHECK_IN,
        "check_out": CHECK_OUT,
        "guests": 2,
        "rooms": 1,
        "currency": "USD",
    }
    values.update(overrides)
    return HotelSearchQuery(**values)


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


async def test_get_hotel_details_returns_quote_for_every_room_type(provider):
    details = await provider.get_hotel_details(
        "hotel-lis-01", check_in=CHECK_IN, check_out=CHECK_OUT, rooms=1, guests=2
    )

    assert details.hotel.hotel_id == "hotel-lis-01"
    assert details.check_in == CHECK_IN
    assert details.check_out == CHECK_OUT
    assert details.cancellation_policy.policy_type == "free"
    assert details.cancellation_policy.refundable is True
    assert details.cancellation_policy.free_cancellation_days == 2
    assert details.cancellation_policy.penalty_nights == 0
    assert [quote.room_type_id for quote in details.room_quotes] == [
        "room-lis-01-std",
        "room-lis-01-suite",
    ]

    standard, suite = details.room_quotes
    assert standard.nightly_rates == [153.32, 154.84, 149.16]
    assert standard.total_price == 457.32
    assert standard.available is True
    assert suite.nightly_rates == [214.61]
    assert suite.total_price is None
    assert suite.available is False
    assert suite.partially_available is True
    assert suite.sold_out_dates == [date(2026, 12, 5), date(2026, 12, 6)]


async def test_get_hotel_details_defaults_to_anchor_date(provider):
    details = await provider.get_hotel_details("hotel-kyo-02")
    assert details.check_in == date(2026, 11, 1)
    assert details.check_out == date(2026, 11, 2)
    assert len(details.room_quotes) == 1


async def test_get_hotel_details_rejects_unknown_hotel(provider):
    with pytest.raises(UnknownHotelError):
        await provider.get_hotel_details("hotel-nope")


async def test_check_availability_reports_fully_sold_out_stay(provider):
    result = await provider.check_availability(
        "hotel-van-03", "room-van-03-std", CHECK_IN, CHECK_OUT, rooms=1
    )

    assert result.nights_requested == 3
    assert result.nights_available == 0
    assert result.available is False
    assert result.nightly_rates == []
    assert result.total_price is None
    assert result.sold_out_dates == [
        date(2026, 12, 4),
        date(2026, 12, 5),
        date(2026, 12, 6),
    ]
    assert result.currency == "USD"


async def test_check_availability_respects_destination_blackout(provider):
    result = await provider.check_availability(
        "hotel-lis-04", "room-lis-04-std", date(2026, 12, 25), date(2026, 12, 26), rooms=1
    )
    assert result.available is False
    assert result.sold_out_dates == [date(2026, 12, 25)]


async def test_check_availability_respects_capacity_below_rooms(provider):
    result = await provider.check_availability(
        "hotel-lis-04", "room-lis-04-std", CHECK_IN, CHECK_OUT, rooms=99
    )
    assert result.available is False
    assert result.nights_available == 0


async def test_check_availability_rejects_unknown_ids(provider):
    with pytest.raises(UnknownHotelError):
        await provider.check_availability("hotel-nope", "room-x", CHECK_IN, CHECK_OUT)
    with pytest.raises(UnknownRoomTypeError):
        await provider.check_availability("hotel-kyo-01", "room-nope", CHECK_IN, CHECK_OUT)


async def test_check_availability_rejects_out_of_window_dates(provider):
    with pytest.raises(InvalidDateError):
        await provider.check_availability(
            "hotel-kyo-01", "room-kyo-01-std", date(2026, 10, 31), date(2026, 11, 2)
        )


async def test_search_rejects_out_of_window_dates(provider):
    with pytest.raises(InvalidDateError):
        await provider.search(
            make_query(check_in=date(2028, 1, 1), check_out=date(2028, 1, 4))
        )


async def test_search_rejects_currency_mismatch(provider):
    with pytest.raises(CurrencyMismatchError):
        await provider.search(make_query(currency="EUR"))


def test_provider_rejects_settings_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        MockHotelProvider(Settings(currency="EUR"))


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


def test_provider_failure_on_missing_dataset(tmp_path):
    settings = Settings(dataset_path=tmp_path / "missing.json")
    with pytest.raises(ProviderError, match="missing.json"):
        MockHotelProvider(settings)


def test_provider_failure_on_corrupt_dataset(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProviderError):
        MockHotelProvider(Settings(dataset_path=path))


def test_provider_failure_on_schema_invalid_dataset(tmp_path):
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    with pytest.raises(ProviderError):
        MockHotelProvider(Settings(dataset_path=path))


def test_settings_from_env_uses_explicit_mapping(tmp_path):
    env = {
        "HOTEL_PROVIDER": "mock",
        "STAYSMART_DATASET_PATH": str(tmp_path / "custom.json"),
        "STAYSMART_LOG_LEVEL": "DEBUG",
        "STAYSMART_CURRENCY": "USD",
        "STAYSMART_WINDOW_DAYS": "90",
    }
    settings = Settings.from_env(env=env)
    assert settings.dataset_path == tmp_path / "custom.json"
    assert settings.log_level == "DEBUG"
    assert settings.window_days == 90


def test_settings_rejects_unknown_provider():
    with pytest.raises(ProviderError):
        Settings.from_env(env={"HOTEL_PROVIDER": "live"})


def test_provider_factory(settings):
    assert isinstance(get_provider(settings), MockHotelProvider)
    with pytest.raises(ProviderError):
        get_provider(Settings(hotel_provider="live"))


def test_configure_logging_is_idempotent():
    configure_logging("WARNING")
    configure_logging("INFO")


async def test_mock_markers_are_present_on_every_returned_object(provider):
    search = await provider.search(make_query(destination="Lisbon"))
    details = await provider.get_hotel_details("hotel-lis-01")
    availability = await provider.check_availability(
        "hotel-lis-01", "room-lis-01-std", CHECK_IN, CHECK_OUT
    )

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
