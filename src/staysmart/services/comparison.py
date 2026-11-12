from datetime import date
from typing import Sequence

import logging

from staysmart.domain.errors import InvalidDateError, UnknownHotelError
from staysmart.domain.models import ComparisonRow, HotelComparison, HotelDetails
from staysmart.providers.base import HotelProvider

PREFERENCE_SCHEME = "preference_not_verified"

logger = logging.getLogger("staysmart")


def _validate_stay_length(check_in: date, check_out: date) -> None:
    nights = (check_out - check_in).days
    if nights < 1:
        raise InvalidDateError("check_out must be after check_in")
    if nights > 30:
        raise InvalidDateError("stay length must be between 1 and 30 nights")


def _verified_text(details: HotelDetails) -> str:
    hotel = details.hotel
    return " ".join(
        [
            hotel.name,
            hotel.location,
            hotel.description,
            *[item.value for item in hotel.amenities],
        ]
    ).lower()


def _row(details: HotelDetails) -> ComparisonRow:
    hotel = details.hotel
    quotable = [quote for quote in details.room_quotes if quote.nights_available > 0]
    nightly_price = (
        min(quote.avg_nightly_rate for quote in quotable) if quotable else None
    )
    available_totals = [
        quote.total_price for quote in details.room_quotes if quote.available
    ]
    return ComparisonRow(
        hotel_id=hotel.hotel_id,
        name=hotel.name,
        nightly_price=nightly_price,
        total_stay_price=min(available_totals) if available_totals else None,
        guest_rating=hotel.guest_rating,
        location=hotel.location,
        amenities=list(hotel.amenities),
        cancellation_policy=hotel.cancellation_policy.policy_type,
        refundable=hotel.cancellation_policy.refundable,
        availability=any(quote.available for quote in details.room_quotes),
    )


def _unmet_preferences(
    preferences: Sequence[str], verified_texts: list[str]
) -> list[str]:
    verified = " ".join(verified_texts)
    return [
        f"{PREFERENCE_SCHEME}:{preference}"
        for preference in preferences
        if preference.strip().lower() not in verified
    ]


async def compare_hotels(
    provider: HotelProvider,
    *,
    hotel_ids: Sequence[str],
    check_in: date,
    check_out: date,
    rooms: int = 1,
    guests: int = 2,
    preferences: Sequence[str] = (),
    currency: str = "USD",
) -> HotelComparison:
    _validate_stay_length(check_in, check_out)
    unique_ids = list(dict.fromkeys(hotel_ids))

    rows: list[ComparisonRow] = []
    unresolved: list[str] = []
    verified_texts: list[str] = []
    resolved_currency: str | None = None
    for hotel_id in unique_ids:
        try:
            details = await provider.get_hotel_details(
                hotel_id,
                check_in=check_in,
                check_out=check_out,
                rooms=rooms,
                guests=guests,
            )
        except UnknownHotelError:
            unresolved.append(hotel_id)
            continue
        rows.append(_row(details))
        verified_texts.append(_verified_text(details))
        if resolved_currency is None:
            resolved_currency = details.currency

    logger.info(
        "compare requested=%d resolved=%d unresolved=%d",
        len(unique_ids),
        len(rows),
        len(unresolved),
    )
    return HotelComparison(
        rows=rows,
        unresolved_hotel_ids=unresolved,
        check_in=check_in,
        check_out=check_out,
        rooms=rooms,
        guests=guests,
        currency=resolved_currency or currency,
        unmet_preferences=_unmet_preferences(preferences, verified_texts),
    )
