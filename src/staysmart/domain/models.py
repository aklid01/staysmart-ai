from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_STAY_NIGHTS = 30


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Amenity(str, Enum):
    WIFI = "WIFI"
    POOL = "POOL"
    GYM = "GYM"
    BREAKFAST = "BREAKFAST"
    PARKING = "PARKING"
    SPA = "SPA"
    PET_FRIENDLY = "PET_FRIENDLY"
    AIR_CONDITIONING = "AIR_CONDITIONING"
    RESTAURANT = "RESTAURANT"
    SHUTTLE = "SHUTTLE"


class CancellationPolicy(StrictModel):
    policy_type: Literal["free", "flexible", "partial", "non_refundable"]
    refundable: bool
    free_cancellation_days: int = Field(ge=0)
    penalty_nights: int = Field(ge=0)
    description: str


class RoomType(StrictModel):
    room_type_id: str
    name: str
    max_occupancy: int = Field(ge=1)
    bed_type: str
    base_nightly_rate: float = Field(gt=0)
    total_rooms: int = Field(ge=1)
    amenities: list[Amenity]


class Destination(StrictModel):
    destination_id: str
    city: str
    country: str
    region: str
    timezone: str


class Hotel(StrictModel):
    hotel_id: str
    name: str
    destination_id: str
    location: str
    star_rating: int = Field(ge=1, le=5)
    guest_rating: float = Field(ge=0, le=10)
    review_count: int = Field(ge=0)
    amenities: list[Amenity]
    room_types: list[RoomType]
    cancellation_policy: CancellationPolicy
    description: str
    currency: str
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class HotelSearchQuery(StrictModel):
    destination: str = Field(min_length=1)
    check_in: date
    check_out: date
    guests: int = Field(default=2, ge=1)
    rooms: int = Field(default=1, ge=1)
    max_nightly_budget: float | None = Field(default=None, gt=0)
    min_rating: float | None = Field(default=None, ge=0, le=10)
    amenities: list[Amenity] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    currency: str = "USD"

    @model_validator(mode="after")
    def validate_stay(self) -> "HotelSearchQuery":
        validate_stay_window(self.check_in, self.check_out)
        return self


class QuoteRequest(StrictModel):
    hotel_id: str
    room_type_id: str
    check_in: date
    check_out: date
    rooms: int = Field(default=1, ge=1)
    guests: int = Field(default=2, ge=1)
    currency: str = "USD"

    @model_validator(mode="after")
    def validate_stay(self) -> "QuoteRequest":
        validate_stay_window(self.check_in, self.check_out)
        return self


class StayQuote(StrictModel):
    hotel_id: str
    room_type_id: str
    check_in: date
    check_out: date
    nights: int
    nightly_rates: list[float]
    avg_nightly_rate: float | None
    total_price: float | None
    currency: str
    guests: int
    rooms: int
    available: bool
    partially_available: bool
    nights_available: int
    sold_out_dates: list[date]
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class HotelSearchHit(StrictModel):
    hotel: Hotel
    quote: StayQuote
    matched_amenities: list[str]
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class HotelSearchResult(StrictModel):
    query: HotelSearchQuery
    results: list[HotelSearchHit]
    total_found: int
    unmet_preferences: list[str]
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class HotelDetails(StrictModel):
    hotel: Hotel
    check_in: date
    check_out: date
    rooms: int
    guests: int
    room_quotes: list[StayQuote]
    cancellation_policy: CancellationPolicy
    currency: str
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class AvailabilityResult(StrictModel):
    hotel_id: str
    room_type_id: str
    check_in: date
    check_out: date
    nights_requested: int
    nights_available: int
    available: bool
    sold_out_dates: list[date]
    nightly_rates: list[float]
    total_price: float | None
    currency: str
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


class ComparisonRow(StrictModel):
    hotel_id: str
    name: str
    nightly_price: float | None
    total_stay_price: float | None
    guest_rating: float
    location: str
    amenities: list[Amenity]
    cancellation_policy: str
    refundable: bool
    availability: bool


class HotelComparison(StrictModel):
    rows: list[ComparisonRow]
    unmet_preferences: list[str]
    data_source: Literal["mock"] = "mock"
    is_live: Literal[False] = False


def validate_stay_window(check_in: date, check_out: date) -> None:
    nights = (check_out - check_in).days
    if nights < 1:
        raise ValueError("check_out must be after check_in")
    if nights > MAX_STAY_NIGHTS:
        raise ValueError(f"stay length must be between 1 and {MAX_STAY_NIGHTS} nights")
