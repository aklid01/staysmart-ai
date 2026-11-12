import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Mapping

from staysmart.domain.errors import InvalidDateError
from staysmart.domain.models import MAX_STAY_NIGHTS, Hotel, QuoteRequest, RoomType, StayQuote


@dataclass(frozen=True)
class InventoryContext:
    currency: str
    anchor_date: date
    window_days: int
    sold_out_overrides: Mapping[str, frozenset[str]]
    blackout_dates: Mapping[str, frozenset[str]]


def validate_date_window(check_in: date, check_out: date, context: InventoryContext) -> None:
    nights = (check_out - check_in).days
    if nights < 1 or nights > MAX_STAY_NIGHTS:
        raise InvalidDateError(
            f"Stay must be between 1 and {MAX_STAY_NIGHTS} nights, got {nights} "
            f"from {check_in} to {check_out}"
        )

    end_exclusive = context.anchor_date + timedelta(days=context.window_days)
    last_night = check_out - timedelta(days=1)
    if check_in < context.anchor_date or last_night >= end_exclusive:
        raise InvalidDateError(
            f"Dates {check_in} to {check_out} are outside the mock dataset window "
            f"{context.anchor_date} to {end_exclusive - timedelta(days=1)}"
        )


def _seed(hotel_id: str, room_type_id: str, day: date) -> int:
    key = f"{hotel_id}:{room_type_id}:{day.isoformat()}"
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")


def _nightly_rate(base_nightly_rate: float, seed: int, day: date) -> float:
    weekend = 1.15 if day.weekday() in (4, 5) else 1.0
    peak = 1.10 if day.month in (7, 8, 12) else 1.0
    jitter = 1.0 + ((seed % 31) - 15) / 100.0
    return round(base_nightly_rate * weekend * peak * jitter, 2)


def inventory_for(
    hotel: Hotel,
    room_type: RoomType,
    request: QuoteRequest,
    context: InventoryContext,
) -> StayQuote:
    validate_date_window(request.check_in, request.check_out, context)

    override_key = f"{hotel.hotel_id}|{room_type.room_type_id}"
    overrides = context.sold_out_overrides.get(override_key, frozenset())
    blackout = context.blackout_dates.get(hotel.destination_id, frozenset())

    nightly_rates: list[float] = []
    sold_out_dates: list[date] = []
    day = request.check_in
    while day < request.check_out:
        seed = _seed(hotel.hotel_id, room_type.room_type_id, day)
        capacity = seed % (room_type.total_rooms + 1)
        if capacity < request.rooms or day.isoformat() in overrides or day.isoformat() in blackout:
            sold_out_dates.append(day)
        else:
            nightly_rates.append(_nightly_rate(room_type.base_nightly_rate, seed, day))
        day += timedelta(days=1)

    nights = (request.check_out - request.check_in).days
    nights_available = len(nightly_rates)
    available = nights_available == nights
    partially_available = 0 < nights_available < nights
    avg_nightly_rate = (
        round(sum(nightly_rates) / nights_available, 2) if nights_available else None
    )
    total_price = round(sum(nightly_rates) * request.rooms, 2) if available else None

    return StayQuote(
        hotel_id=hotel.hotel_id,
        room_type_id=room_type.room_type_id,
        check_in=request.check_in,
        check_out=request.check_out,
        nights=nights,
        nightly_rates=nightly_rates,
        avg_nightly_rate=avg_nightly_rate,
        total_price=total_price,
        currency=context.currency,
        guests=request.guests,
        rooms=request.rooms,
        available=available,
        partially_available=partially_available,
        nights_available=nights_available,
        sold_out_dates=sold_out_dates,
    )
