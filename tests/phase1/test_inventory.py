from datetime import date, timedelta

import pytest

from staysmart.domain.errors import InvalidDateError
from staysmart.domain.models import QuoteRequest
from staysmart.providers.mock.inventory import inventory_for, validate_date_window

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)


def make_quote(dataset, hotel_id, room_type_id, *, rooms=1, check_in=CHECK_IN, check_out=CHECK_OUT):
    hotel = dataset.hotels_by_id[hotel_id]
    room = next(item for item in hotel.room_types if item.room_type_id == room_type_id)
    request = QuoteRequest(
        hotel_id=hotel_id,
        room_type_id=room_type_id,
        check_in=check_in,
        check_out=check_out,
        rooms=rooms,
        guests=2,
        currency="USD",
    )
    return inventory_for(hotel, room, request, dataset.context)


def test_inventory_is_deterministic(dataset):
    first = make_quote(dataset, "hotel-lis-01", "room-lis-01-std")
    second = make_quote(dataset, "hotel-lis-01", "room-lis-01-std")
    assert first == second
    assert first.nightly_rates == second.nightly_rates


def test_inventory_matches_contract_reference_rates(dataset):
    quote = make_quote(dataset, "hotel-kyo-01", "room-kyo-01-std")
    assert quote.nights == 3
    assert quote.nightly_rates == [252.75, 215.82]
    assert quote.avg_nightly_rate == 234.28
    assert quote.total_price is None
    assert quote.available is False
    assert quote.partially_available is True
    assert quote.nights_available == 2
    assert quote.sold_out_dates == [date(2026, 12, 5)]
    assert quote.data_source == "mock"
    assert quote.is_live is False


def test_partial_stay_never_invents_a_total_price(dataset):
    quote = make_quote(dataset, "hotel-lis-02", "room-lis-02-std")
    assert quote.nightly_rates == [128.35, 85.17]
    assert quote.avg_nightly_rate == 106.76
    assert quote.total_price is None
    assert quote.partially_available is True


def test_fully_sold_out_stay_has_no_rates_or_total(dataset):
    quote = make_quote(dataset, "hotel-van-03", "room-van-03-std")
    assert quote.nightly_rates == []
    assert quote.avg_nightly_rate is None
    assert quote.total_price is None
    assert quote.available is False
    assert quote.partially_available is False
    assert quote.sold_out_dates == [
        date(2026, 12, 4),
        date(2026, 12, 5),
        date(2026, 12, 6),
    ]


def test_blackout_date_is_sold_out(dataset):
    quote = make_quote(
        dataset,
        "hotel-lis-04",
        "room-lis-04-std",
        check_in=date(2026, 12, 25),
        check_out=date(2026, 12, 26),
    )
    assert quote.available is False
    assert quote.sold_out_dates == [date(2026, 12, 25)]


def test_capacity_below_rooms_marks_every_night_sold_out(dataset):
    quote = make_quote(dataset, "hotel-lis-04", "room-lis-04-std", rooms=99)
    assert quote.nights_available == 0
    assert quote.nightly_rates == []
    assert len(quote.sold_out_dates) == 3


def test_total_price_multiplies_by_rooms(dataset):
    single = make_quote(dataset, "hotel-lis-01", "room-lis-01-std", rooms=1)
    double = make_quote(dataset, "hotel-lis-01", "room-lis-01-std", rooms=2)
    assert single.total_price == 457.32
    assert double.total_price == round(457.32 * 2, 2)


def test_validate_date_window_rejects_out_of_range_dates(dataset):
    with pytest.raises(InvalidDateError):
        validate_date_window(date(2026, 10, 31), date(2026, 11, 2), dataset.context)
    with pytest.raises(InvalidDateError):
        validate_date_window(date(2028, 1, 1), date(2028, 1, 3), dataset.context)


def test_validate_date_window_rejects_stays_over_30_nights(dataset):
    with pytest.raises(InvalidDateError):
        validate_date_window(CHECK_IN, CHECK_IN + timedelta(days=31), dataset.context)


def test_validate_date_window_accepts_valid_stay(dataset):
    validate_date_window(CHECK_IN, CHECK_OUT, dataset.context)
