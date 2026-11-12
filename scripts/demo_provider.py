import asyncio
import json
from datetime import date
from pathlib import Path

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.domain.models import Amenity, HotelSearchQuery, StayQuote
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import get_provider

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)
ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "provider_demo.json"


def iso_dates(values: list[date]) -> list[str]:
    return [value.isoformat() for value in values]


def quote_summary(quote: StayQuote) -> dict:
    return {
        "room_type_id": quote.room_type_id,
        "nights": quote.nights,
        "nights_available": quote.nights_available,
        "nightly_rates": quote.nightly_rates,
        "avg_nightly_rate": quote.avg_nightly_rate,
        "total_price": quote.total_price,
        "available": quote.available,
        "partially_available": quote.partially_available,
        "sold_out_dates": iso_dates(quote.sold_out_dates),
    }


def hit_summary(hit) -> dict:
    summary = quote_summary(hit.quote)
    summary.update(
        {
            "hotel_id": hit.hotel.hotel_id,
            "hotel_name": hit.hotel.name,
            "location": hit.hotel.location,
            "guest_rating": hit.hotel.guest_rating,
            "star_rating": hit.hotel.star_rating,
            "amenities": [item.value for item in hit.hotel.amenities],
            "matched_amenities": hit.matched_amenities,
            "cancellation_policy": hit.hotel.cancellation_policy.policy_type,
            "refundable": hit.hotel.cancellation_policy.refundable,
            "currency": hit.quote.currency,
            "data_source": hit.quote.data_source,
            "is_live": hit.quote.is_live,
        }
    )
    return summary


def search_summary(query: HotelSearchQuery, result) -> dict:
    return {
        "destination": query.destination,
        "check_in": query.check_in.isoformat(),
        "check_out": query.check_out.isoformat(),
        "guests": query.guests,
        "rooms": query.rooms,
        "max_nightly_budget": query.max_nightly_budget,
        "min_rating": query.min_rating,
        "required_amenities": [item.value for item in query.amenities],
        "preferences": query.preferences,
        "total_found": result.total_found,
        "hotel_ids": [hit.hotel.hotel_id for hit in result.results],
        "unmet_preferences": result.unmet_preferences,
        "hits": [hit_summary(hit) for hit in result.results],
    }


def details_summary(details) -> dict:
    policy = details.cancellation_policy
    return {
        "hotel_id": details.hotel.hotel_id,
        "hotel_name": details.hotel.name,
        "check_in": details.check_in.isoformat(),
        "check_out": details.check_out.isoformat(),
        "rooms": details.rooms,
        "guests": details.guests,
        "currency": details.currency,
        "cancellation_policy": policy.policy_type,
        "refundable": policy.refundable,
        "free_cancellation_days": policy.free_cancellation_days,
        "penalty_nights": policy.penalty_nights,
        "data_source": details.data_source,
        "is_live": details.is_live,
        "room_quotes": [quote_summary(quote) for quote in details.room_quotes],
    }


def availability_summary(result) -> dict:
    return {
        "hotel_id": result.hotel_id,
        "room_type_id": result.room_type_id,
        "check_in": result.check_in.isoformat(),
        "check_out": result.check_out.isoformat(),
        "rooms": 1,
        "currency": result.currency,
        "data_source": result.data_source,
        "is_live": result.is_live,
        "nights_requested": result.nights_requested,
        "nights_available": result.nights_available,
        "available": result.available,
        "sold_out_dates": iso_dates(result.sold_out_dates),
        "nightly_rates": result.nightly_rates,
        "total_price": result.total_price,
    }


async def run() -> None:
    settings = Settings()
    provider = get_provider(settings)
    dataset = load_dataset(settings.dataset_path)

    kyoto_query = HotelSearchQuery(
        destination="Kyoto",
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=2,
        rooms=1,
        max_nightly_budget=250.0,
        min_rating=8.0,
        amenities=[Amenity.WIFI, Amenity.BREAKFAST],
        preferences=["quiet room"],
        currency=settings.currency,
    )
    lisbon_query = HotelSearchQuery(
        destination="Lisbon",
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=2,
        rooms=1,
        max_nightly_budget=160.0,
        min_rating=7.0,
        amenities=[Amenity.WIFI],
        currency=settings.currency,
    )

    kyoto = await provider.search(kyoto_query)
    lisbon = await provider.search(lisbon_query)
    details = await provider.get_hotel_details(
        "hotel-lis-01", check_in=CHECK_IN, check_out=CHECK_OUT, rooms=1, guests=2
    )
    availability = await provider.check_availability(
        "hotel-van-03", "room-van-03-std", CHECK_IN, CHECK_OUT, rooms=1
    )

    payload = {
        "artifact_version": 1,
        "dataset_schema_version": dataset.schema_version,
        "currency": settings.currency,
        "data_source": "mock",
        "is_live": False,
        "searches": {
            "kyoto_family": search_summary(kyoto_query, kyoto),
            "lisbon_budget": search_summary(lisbon_query, lisbon),
        },
        "details": details_summary(details),
        "availability": availability_summary(availability),
    }

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT_PATH}")
    print(f"kyoto_found={kyoto.total_found} lisbon_found={lisbon.total_found}")
    print(f"availability_available={availability.available}")


if __name__ == "__main__":
    asyncio.run(run())
