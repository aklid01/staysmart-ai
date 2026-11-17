import logging
from datetime import date
from typing import Sequence

from staysmart.domain.errors import CurrencyMismatchError, UnknownHotelError
from staysmart.domain.models import (
    ComparisonRow,
    HotelComparison,
    HotelDetails,
    unverified_preferences,
    validate_stay_dates,
)
from staysmart.providers.base import HotelProvider

logger = logging.getLogger("staysmart")


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
    nightly_price = min(quote.avg_nightly_rate for quote in quotable) if quotable else None
    available_totals = [quote.total_price for quote in details.room_quotes if quote.available]
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
    validate_stay_dates(check_in, check_out)
    unique_ids = list(dict.fromkeys(hotel_ids))

    resolved: list[HotelDetails] = []
    unresolved: list[str] = []
    for hotel_id in unique_ids:
        try:
            resolved.append(
                await provider.get_hotel_details(
                    hotel_id,
                    check_in=check_in,
                    check_out=check_out,
                    rooms=rooms,
                    guests=guests,
                )
            )
        except UnknownHotelError:
            unresolved.append(hotel_id)

    currencies = {details.currency for details in resolved}
    if len(currencies) > 1:
        raise CurrencyMismatchError(
            f"cannot compare hotels priced in different currencies: {', '.join(sorted(currencies))}"
        )
    currency = next(iter(currencies)) if currencies else currency

    rows = [_row(details) for details in resolved]
    verified_texts = [_verified_text(details) for details in resolved]

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
        currency=currency,
        unmet_preferences=unverified_preferences(preferences, verified_texts),
    )
