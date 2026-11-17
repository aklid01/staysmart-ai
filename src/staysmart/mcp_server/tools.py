import functools
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, ParamSpec

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.server import MCPServer

from staysmart.config import Settings
from staysmart.domain.errors import InvalidArgumentError, StaySmartError
from staysmart.domain.models import (
    Amenity,
    AvailabilityResult,
    HotelComparison,
    HotelDetails,
    HotelPolicyInfo,
    HotelSearchQuery,
    HotelSearchResult,
    validate_stay_dates,
)
from staysmart.providers.base import HotelProvider
from staysmart.services import comparison as comparison_service
from staysmart.services import policies as policies_service

P = ParamSpec("P")


def tool_errors(fn: Callable[P, Awaitable[Any]]) -> Callable[P, Awaitable[Any]]:
    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs):
        try:
            return await fn(*args, **kwargs)
        except StaySmartError as exc:
            raise ToolError(f"{exc.code}: {exc.message}") from exc

    return wrapper


def register_tools(server: MCPServer, settings: Settings, provider: HotelProvider) -> None:
    @server.tool()
    @tool_errors
    async def search_hotels(
        destination: str,
        check_in: date,
        check_out: date,
        guests: int = 2,
        rooms: int = 1,
        max_nightly_budget: float | None = None,
        min_rating: float | None = None,
        amenities: list[Amenity] | None = None,
        preferences: list[str] | None = None,
    ) -> HotelSearchResult:
        """Search hotels in a destination for a stay.

        Filters by nightly budget, minimum guest rating and required amenities; free-text preferences
        are reported when unverifiable. Returns one best quote per hotel with availability flags,
        sold-out dates and mock data markers. Raises an error result for unknown destinations or
        invalid date ranges.
        """
        validate_stay_dates(check_in, check_out)
        query = HotelSearchQuery(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
            max_nightly_budget=max_nightly_budget,
            min_rating=min_rating,
            amenities=amenities or [],
            preferences=preferences or [],
            currency=settings.currency,
        )
        return await provider.search(query)

    @server.tool()
    @tool_errors
    async def get_hotel_details(
        hotel_id: str,
        check_in: date | None = None,
        check_out: date | None = None,
        rooms: int = 1,
        guests: int = 2,
    ) -> HotelDetails:
        """Get full details for one hotel.

        Description, amenities, room types with quotes for the stay dates, and the cancellation
        policy. Without dates it quotes a single night at the dataset anchor date. Raises an error
        result for unknown hotel ids.
        """
        return await provider.get_hotel_details(
            hotel_id,
            check_in=check_in,
            check_out=check_out,
            rooms=rooms,
            guests=guests,
        )

    @server.tool()
    @tool_errors
    async def check_availability(
        hotel_id: str,
        room_type_id: str,
        check_in: date,
        check_out: date,
        rooms: int = 1,
        guests: int = 2,
    ) -> AvailabilityResult:
        """Check per-night availability and pricing for one room type over a date range.

        Sold-out or partially available stays are normal results carrying sold-out dates and no
        invented total price. Raises an error result for unknown hotel or room type ids and invalid
        dates.
        """
        return await provider.check_availability(
            hotel_id, room_type_id, check_in, check_out, rooms=rooms, guests=guests
        )

    @server.tool()
    @tool_errors
    async def compare_hotels(
        hotel_ids: list[str],
        check_in: date,
        check_out: date,
        rooms: int = 1,
        guests: int = 2,
        preferences: list[str] | None = None,
    ) -> HotelComparison:
        """Compare several hotels side by side for the same stay.

        Nightly price, total stay price, guest rating, location, amenities, cancellation policy and
        availability. Unknown ids are reported in unresolved_hotel_ids instead of failing the call.
        Raises an error result for invalid date ranges.
        """
        if not hotel_ids:
            raise InvalidArgumentError("hotel_ids must contain at least one hotel id")
        return await comparison_service.compare_hotels(
            provider,
            hotel_ids=hotel_ids,
            check_in=check_in,
            check_out=check_out,
            rooms=rooms,
            guests=guests,
            preferences=preferences or [],
            currency=settings.currency,
        )

    @server.tool()
    @tool_errors
    async def get_hotel_policies(hotel_id: str) -> HotelPolicyInfo:
        """Get grounded policy facts for one hotel.

        Cancellation and refund terms, pet policy derived from amenities, and explicit information
        gaps for anything the provider does not supply (check-in and check-out times). Raises an
        error result for unknown hotel ids.
        """
        return await policies_service.get_hotel_policies(provider, hotel_id)
