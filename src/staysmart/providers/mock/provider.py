import logging
import math
from dataclasses import replace
from datetime import date, timedelta

from staysmart.config import Settings
from staysmart.domain.errors import (
    CurrencyMismatchError,
    ProviderError,
    UnknownDestinationError,
    UnknownHotelError,
    UnknownRoomTypeError,
)
from staysmart.domain.models import (
    Amenity,
    AvailabilityResult,
    Hotel,
    HotelDetails,
    HotelSearchHit,
    HotelSearchQuery,
    HotelSearchResult,
    QuoteRequest,
    RoomType,
    StayQuote,
    unverified_preferences,
)
from staysmart.providers.base import HotelProvider
from staysmart.providers.mock.dataset import MockDataset, load_dataset
from staysmart.providers.mock.inventory import (
    InventoryContext,
    inventory_for,
    validate_date_window,
)

logger = logging.getLogger("staysmart")


def _price_key(quote_avg: float | None) -> float:
    return quote_avg if quote_avg is not None else math.inf


class MockHotelProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._dataset: MockDataset = load_dataset(settings.dataset_path)
        if settings.currency.upper() != self._dataset.currency.upper():
            raise CurrencyMismatchError(
                f"Settings currency {settings.currency!r} does not match "
                f"mock dataset currency {self._dataset.currency!r}"
            )
        self._context: InventoryContext = replace(
            self._dataset.context,
            window_days=min(self._dataset.window_days, settings.window_days),
        )

    async def search(self, query: HotelSearchQuery) -> HotelSearchResult:
        self._validate_currency(query.currency)
        validate_date_window(query.check_in, query.check_out, self._context)

        destination_ids = self._match_destinations(query.destination)
        if not destination_ids:
            logger.warning("search rejected unknown destination=%s", query.destination)
            raise UnknownDestinationError(f"No destination matches {query.destination!r} in the mock dataset")

        hits = self._collect_hits(query, destination_ids)
        hits.sort(
            key=lambda hit: (
                not hit.quote.available,
                _price_key(hit.quote.avg_nightly_rate),
                hit.hotel.hotel_id,
            )
        )
        logger.info(
            "search destination=%s check_in=%s check_out=%s found=%d",
            query.destination,
            query.check_in,
            query.check_out,
            len(hits),
        )
        return HotelSearchResult(
            query=query,
            results=hits,
            total_found=len(hits),
            unmet_preferences=self._unmet_preferences(query, hits),
        )

    def _collect_hits(self, query: HotelSearchQuery, destination_ids: set[str]) -> list[HotelSearchHit]:
        required = set(query.amenities)
        hits: list[HotelSearchHit] = []
        for hotel in self._dataset.hotels:
            if not self._matches_filters(hotel, query, destination_ids, required):
                continue
            best = self._best_quote(hotel, query)
            if best is None:
                continue
            matched = sorted(item.value for item in required if item in hotel.amenities)
            hits.append(HotelSearchHit(hotel=hotel, quote=best, matched_amenities=matched))
        return hits

    @staticmethod
    def _matches_filters(
        hotel: Hotel,
        query: HotelSearchQuery,
        destination_ids: set[str],
        required: set[Amenity],
    ) -> bool:
        if hotel.destination_id not in destination_ids:
            return False
        if query.min_rating is not None and hotel.guest_rating < query.min_rating:
            return False
        return required.issubset(set(hotel.amenities))

    def _best_quote(self, hotel: Hotel, query: HotelSearchQuery) -> StayQuote | None:
        quotes = []
        for room in hotel.room_types:
            if room.max_occupancy * query.rooms < query.guests:
                continue
            quote = self._quote(
                hotel,
                room,
                query.check_in,
                query.check_out,
                query.rooms,
                query.guests,
                query.currency,
            )
            if query.max_nightly_budget is not None and (
                quote.avg_nightly_rate is None or quote.avg_nightly_rate > query.max_nightly_budget
            ):
                continue
            quotes.append(quote)

        if not quotes:
            return None
        return min(
            quotes,
            key=lambda item: (
                not item.available,
                _price_key(item.avg_nightly_rate),
                item.room_type_id,
            ),
        )

    async def get_hotel_details(
        self,
        hotel_id: str,
        *,
        check_in: date | None = None,
        check_out: date | None = None,
        rooms: int = 1,
        guests: int = 2,
    ) -> HotelDetails:
        hotel = self._hotel(hotel_id)
        start = check_in or self._dataset.anchor_date
        end = check_out or (start + timedelta(days=1))
        validate_date_window(start, end, self._context)

        quotes = [
            self._quote(hotel, room, start, end, rooms, guests, self._settings.currency) for room in hotel.room_types
        ]
        logger.info("details hotel_id=%s room_types=%d", hotel_id, len(quotes))
        return HotelDetails(
            hotel=hotel,
            check_in=start,
            check_out=end,
            rooms=rooms,
            guests=guests,
            room_quotes=quotes,
            cancellation_policy=hotel.cancellation_policy,
            currency=self._settings.currency,
        )

    async def check_availability(
        self,
        hotel_id: str,
        room_type_id: str,
        check_in: date,
        check_out: date,
        rooms: int = 1,
        guests: int = 2,
    ) -> AvailabilityResult:
        hotel = self._hotel(hotel_id)
        room = next(
            (item for item in hotel.room_types if item.room_type_id == room_type_id),
            None,
        )
        if room is None:
            logger.warning(
                "availability rejected unknown room_type_id=%s hotel_id=%s",
                room_type_id,
                hotel_id,
            )
            raise UnknownRoomTypeError(f"Unknown room_type_id {room_type_id!r} for hotel {hotel_id!r}")

        validate_date_window(check_in, check_out, self._context)
        quote = self._quote(hotel, room, check_in, check_out, rooms, guests, self._settings.currency)
        logger.info(
            "availability hotel_id=%s room_type_id=%s nights_available=%d/%d",
            hotel_id,
            room_type_id,
            quote.nights_available,
            quote.nights,
        )
        return AvailabilityResult(
            hotel_id=hotel_id,
            room_type_id=room_type_id,
            check_in=check_in,
            check_out=check_out,
            nights_requested=quote.nights,
            nights_available=quote.nights_available,
            available=quote.available,
            sold_out_dates=quote.sold_out_dates,
            nightly_rates=quote.nightly_rates,
            total_price=quote.total_price,
            currency=quote.currency,
        )

    def _quote(
        self,
        hotel: Hotel,
        room: RoomType,
        check_in: date,
        check_out: date,
        rooms: int,
        guests: int,
        currency: str,
    ):
        request = QuoteRequest(
            hotel_id=hotel.hotel_id,
            room_type_id=room.room_type_id,
            check_in=check_in,
            check_out=check_out,
            rooms=rooms,
            guests=guests,
            currency=currency,
        )
        return inventory_for(hotel, room, request, self._context)

    def _hotel(self, hotel_id: str) -> Hotel:
        hotel = self._dataset.hotels_by_id.get(hotel_id)
        if hotel is None:
            logger.warning("unknown hotel_id=%s", hotel_id)
            raise UnknownHotelError(f"Unknown hotel_id {hotel_id!r} in the mock dataset")
        return hotel

    def _validate_currency(self, currency: str) -> None:
        if currency.upper() != self._dataset.currency.upper():
            raise CurrencyMismatchError(
                f"Query currency {currency!r} does not match mock dataset currency {self._dataset.currency!r}"
            )

    def _match_destinations(self, destination: str) -> set[str]:
        needle = destination.strip().lower()
        matched: set[str] = set()
        for item in self._dataset.destinations:
            candidates = (
                item.destination_id,
                item.city,
                item.country,
                item.region,
            )
            if any(needle == value.lower() or needle in value.lower() for value in candidates):
                matched.add(item.destination_id)
        return matched

    def _unmet_preferences(self, query: HotelSearchQuery, hits: list[HotelSearchHit]) -> list[str]:
        if not hits:
            messages = [f"no_hotels_matched:{query.destination}"]
            if query.max_nightly_budget is not None:
                messages.append(f"filter:max_nightly_budget={query.max_nightly_budget}")
            if query.min_rating is not None:
                messages.append(f"filter:min_rating={query.min_rating}")
            if query.amenities:
                joined = ",".join(sorted(item.value for item in query.amenities))
                messages.append(f"filter:amenities={joined}")
            return messages

        verified_texts = [
            " ".join(
                [
                    hit.hotel.name,
                    hit.hotel.location,
                    hit.hotel.description,
                    *[item.value for item in hit.hotel.amenities],
                ]
            )
            for hit in hits
        ]
        return unverified_preferences(query.preferences, verified_texts)


def build_provider(settings: Settings) -> HotelProvider:
    if settings.hotel_provider != "mock":
        raise ProviderError(f"Unsupported hotel provider {settings.hotel_provider!r}; only 'mock' is available")
    return MockHotelProvider(settings)
