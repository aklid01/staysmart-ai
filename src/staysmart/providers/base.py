from datetime import date
from typing import Protocol

from staysmart.domain.models import (
    AvailabilityResult,
    HotelDetails,
    HotelSearchQuery,
    HotelSearchResult,
)


class HotelProvider(Protocol):
    async def search(self, query: HotelSearchQuery) -> HotelSearchResult: ...

    async def get_hotel_details(
        self,
        hotel_id: str,
        *,
        check_in: date | None = None,
        check_out: date | None = None,
        rooms: int = 1,
        guests: int = 2,
    ) -> HotelDetails: ...

    async def check_availability(
        self,
        hotel_id: str,
        room_type_id: str,
        check_in: date,
        check_out: date,
        rooms: int = 1,
        guests: int = 2,
    ) -> AvailabilityResult: ...
