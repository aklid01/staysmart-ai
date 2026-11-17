import asyncio
from datetime import date

from demo_summaries import (
    availability_summary,
    details_summary,
    search_summary,
    write_artifact,
)

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.domain.models import Amenity, HotelSearchQuery
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import build_provider

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)
ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "provider_demo.json"


async def run() -> None:
    settings = Settings()
    provider = build_provider(settings)
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
    availability = await provider.check_availability("hotel-van-03", "room-van-03-std", CHECK_IN, CHECK_OUT, rooms=1)

    payload = {
        "artifact_version": 1,
        "dataset_schema_version": dataset.schema_version,
        "currency": settings.currency,
        "data_source": "mock",
        "is_live": False,
        "searches": {
            "kyoto_family": search_summary(kyoto.model_dump(mode="json")),
            "lisbon_budget": search_summary(lisbon.model_dump(mode="json")),
        },
        "details": details_summary(details.model_dump(mode="json")),
        "availability": availability_summary(availability.model_dump(mode="json"), rooms=1),
    }

    write_artifact(ARTIFACT_PATH, payload)
    print(f"kyoto_found={kyoto.total_found} lisbon_found={lisbon.total_found}")
    print(f"availability_available={availability.available}")


if __name__ == "__main__":
    asyncio.run(run())
