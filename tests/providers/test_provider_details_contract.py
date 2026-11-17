from datetime import date

import pytest
from query import CHECK_IN, CHECK_OUT

from staysmart.domain.errors import (
    InvalidDateError,
    UnknownHotelError,
    UnknownRoomTypeError,
)


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
    result = await provider.check_availability("hotel-van-03", "room-van-03-std", CHECK_IN, CHECK_OUT, rooms=1)

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
    result = await provider.check_availability("hotel-lis-04", "room-lis-04-std", CHECK_IN, CHECK_OUT, rooms=99)
    assert result.available is False
    assert result.nights_available == 0


async def test_check_availability_rejects_unknown_ids(provider):
    with pytest.raises(UnknownHotelError):
        await provider.check_availability("hotel-nope", "room-x", CHECK_IN, CHECK_OUT)
    with pytest.raises(UnknownRoomTypeError):
        await provider.check_availability("hotel-kyo-01", "room-nope", CHECK_IN, CHECK_OUT)


async def test_check_availability_rejects_out_of_window_dates(provider):
    with pytest.raises(InvalidDateError):
        await provider.check_availability("hotel-kyo-01", "room-kyo-01-std", date(2026, 10, 31), date(2026, 11, 2))
