from datetime import date

import pytest

from staysmart.domain.errors import InvalidDateError, UnknownHotelError
from staysmart.services.comparison import compare_hotels

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)


async def test_compare_returns_rows_in_requested_order_with_pinned_values(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01", "hotel-lis-02"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    assert [row.hotel_id for row in comparison.rows] == ["hotel-lis-01", "hotel-lis-02"]
    assert comparison.unresolved_hotel_ids == []
    assert comparison.check_in == CHECK_IN
    assert comparison.check_out == CHECK_OUT
    assert comparison.rooms == 1
    assert comparison.guests == 2
    assert comparison.currency == "USD"
    assert comparison.data_source == "mock"
    assert comparison.is_live is False

    first = comparison.rows[0]
    assert first.name == "Alfama Riverside Boutique"
    assert first.location == "Alfama, Lisbon"
    assert first.guest_rating == 8.7
    assert first.amenities == ["WIFI", "BREAKFAST", "AIR_CONDITIONING", "RESTAURANT"]
    assert first.cancellation_policy == "free"
    assert first.refundable is True
    assert first.nightly_price == 152.44
    assert first.total_stay_price == 457.32
    assert first.availability is True


async def test_compare_nightly_price_is_minimum_across_room_quotes(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    row = comparison.rows[0]
    assert row.nightly_price == 152.44
    assert row.total_stay_price == 457.32


async def test_compare_reports_no_total_when_no_room_is_fully_available(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-02"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    row = comparison.rows[0]
    assert row.nightly_price == 106.76
    assert row.total_stay_price is None
    assert row.availability is False


async def test_compare_moves_unknown_ids_to_unresolved_and_keeps_known_rows(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-xxx-99", "hotel-lis-02", "hotel-missing-42"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    assert [row.hotel_id for row in comparison.rows] == ["hotel-lis-02"]
    assert comparison.unresolved_hotel_ids == ["hotel-xxx-99", "hotel-missing-42"]


async def test_compare_with_every_id_unknown_is_a_success_with_empty_rows(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-xxx-99"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    assert comparison.rows == []
    assert comparison.unresolved_hotel_ids == ["hotel-xxx-99"]
    assert comparison.data_source == "mock"


async def test_compare_dedupes_ids_preserving_first_occurrence(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01", "hotel-lis-01", "hotel-lis-02"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )

    assert [row.hotel_id for row in comparison.rows] == ["hotel-lis-01", "hotel-lis-02"]
    assert comparison.unresolved_hotel_ids == []


async def test_compare_reports_unverified_free_text_preferences(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01", "hotel-lis-02"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        preferences=["river view"],
    )

    assert comparison.unmet_preferences == ["preference_not_verified:river view"]


async def test_compare_accepts_verified_preferences_silently(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        preferences=["riverside"],
    )

    assert comparison.unmet_preferences == []


async def test_compare_rejects_reversed_dates_before_resolving_hotels(provider):
    with pytest.raises(InvalidDateError):
        await compare_hotels(
            provider,
            hotel_ids=["hotel-xxx-99", "hotel-missing-42"],
            check_in=CHECK_OUT,
            check_out=CHECK_IN,
        )


async def test_compare_rejects_stays_longer_than_thirty_nights(provider):
    with pytest.raises(InvalidDateError):
        await compare_hotels(
            provider,
            hotel_ids=["hotel-lis-01"],
            check_in=date(2026, 12, 1),
            check_out=date(2027, 1, 5),
        )


async def test_compare_rejects_dates_outside_booking_window_via_provider(provider):
    with pytest.raises(InvalidDateError):
        await compare_hotels(
            provider,
            hotel_ids=["hotel-lis-01"],
            check_in=date(2027, 11, 1),
            check_out=date(2027, 11, 3),
        )


async def test_compare_unknown_hotel_error_is_absorbed_per_id(provider):
    comparison = await compare_hotels(
        provider,
        hotel_ids=["hotel-lis-01"],
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
    )
    assert comparison.unresolved_hotel_ids == []

    with pytest.raises(UnknownHotelError):
        await provider.get_hotel_details("hotel-xxx-99")
