# Phase 1 provider contract and failure modes

This document is the specification for Phase 1. It is written before the provider implementation. Tests and the golden E2E artifact are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 1 delivers typed hotel domain models, explicit configuration, a versioned mock dataset, a deterministic date-aware inventory algorithm, and an in-process async `HotelProvider` with three operations. No MCP server, HTTP service, RAG, agent or frontend exists in this phase.

All data is mock. Every result object carries `data_source="mock"` and `is_live=False`. No fact, price or availability value may be invented. Missing availability is reported as missing, never filled in.

## Dataset fixture

`data/hotels/v1/hotels.json`:

- `schema_version = 1`, `dataset_name = "Mock hotel dataset v1"`, `currency = "USD"`.
- `anchor_date = 2026-11-01`, `window_days = 365`. Valid booking dates are `[anchor_date, anchor_date + min(dataset.window_days, settings.window_days))`.
- 3 destinations: `lisbon-pt` (Lisbon, Portugal, Europe), `kyoto-jp` (Kyoto, Japan, Asia), `vancouver-ca` (Vancouver, Canada, North America).
- 10 hotels, 13 room types. Ratings span 6.8 to 9.4, base nightly rates span 55.0 to 340.0, cancellation policies cover free, flexible, partial and non_refundable.
- `sold_out_overrides` is keyed by `hotel_id|room_type_id`. Values are ISO dates.
  - `hotel-kyo-01|room-kyo-01-std`: `2026-12-05`
  - `hotel-lis-01|room-lis-01-suite`: `2026-12-06`
  - `hotel-van-03|room-van-03-std`: `2026-12-04`, `2026-12-05`, `2026-12-06`
- `blackout_dates` is keyed by destination. `lisbon-pt`: `2026-12-25`.

## Inventory algorithm

For a `QuoteRequest` and an `InventoryContext`, `inventory_for(hotel, room_type, request, context)` is pure and deterministic.

```
seed(hotel_id, room_type_id, day) = int.from_bytes(sha256(f"{hotel_id}:{room_type_id}:{day.isoformat()}").digest()[:8], "big")
weekend = 1.15 if day.weekday() in (4, 5) else 1.0
peak    = 1.10 if day.month in (7, 8, 12) else 1.0
jitter  = 1.0 + ((seed % 31) - 15) / 100
rate    = round(base_nightly_rate * weekend * peak * jitter, 2)
capacity = seed % (total_rooms + 1)
sold_out = capacity < rooms OR day in sold_out_overrides[hotel_id|room_type_id] OR day in blackout_dates[destination_id]
```

Use `hashlib.sha256`, never Python's randomized `hash()`. No `datetime.now()` anywhere in provider code.

For each night in `[check_in, check_out)`:

- Available nights contribute their rate to `nightly_rates` in date order.
- Sold-out nights contribute their ISO date to `sold_out_dates` in date order.
- `nights = (check_out - check_in).days`, `nights_available = len(nightly_rates)`.
- `available = nights_available == nights`.
- `partially_available = 0 < nights_available < nights`.
- `avg_nightly_rate = round(sum(nightly_rates) / nights_available, 2)` when any night is available, otherwise `None`.
- `total_price = round(sum(nightly_rates) * rooms, 2)` only when `available`, otherwise `None`.

A partial or fully sold-out stay never reports a total price. `validate_date_window` rejects stays shorter than 1 night, longer than 30 nights, or dates outside the booking window with `InvalidDateError`.

## Domain models

`src/staysmart/domain/models.py` uses pydantic v2 with `extra="forbid"`:

- `Amenity(str, Enum)`: WIFI, POOL, GYM, BREAKFAST, PARKING, SPA, PET_FRIENDLY, AIR_CONDITIONING, RESTAURANT, SHUTTLE.
- `CancellationPolicy`: policy_type, refundable, free_cancellation_days, penalty_nights, description.
- `RoomType`: room_type_id, name, max_occupancy, bed_type, base_nightly_rate, total_rooms, amenities.
- `Destination`: destination_id, city, country, region, timezone.
- `Hotel`: hotel_id, name, destination_id, location, star_rating, guest_rating, review_count, amenities, room_types, cancellation_policy, description, currency, data_source, is_live.
- `HotelSearchQuery`: destination, check_in, check_out, guests >= 1, rooms >= 1, `max_nightly_budget > 0 | None`, `min_rating` 0 to 10 `| None`, amenities, preferences, currency. Validators reject `check_out <= check_in` and stays longer than 30 nights.
- `QuoteRequest`: hotel_id, room_type_id, check_in, check_out, rooms >= 1, guests >= 1, currency, with the same stay validators.
- `StayQuote`: hotel_id, room_type_id, check_in, check_out, nights, nightly_rates, avg_nightly_rate, total_price, currency, guests, rooms, available, partially_available, nights_available, sold_out_dates, data_source, is_live.
- `HotelSearchHit`: hotel, quote, matched_amenities, data_source, is_live.
- `HotelSearchResult`: query, results, total_found, unmet_preferences, data_source, is_live.
- `HotelDetails`: hotel, check_in, check_out, rooms, guests, room_quotes, cancellation_policy, currency, data_source, is_live.
- `AvailabilityResult`: hotel_id, room_type_id, check_in, check_out, nights_requested, nights_available, available, sold_out_dates, nightly_rates, total_price, currency, data_source, is_live.
- `ComparisonRow` and `HotelComparison`: types only, no logic in Phase 1.

## Provider interface

`src/staysmart/providers/base.py` defines `HotelProvider(Protocol)`:

```
async search(query: HotelSearchQuery) -> HotelSearchResult
async get_hotel_details(hotel_id: str, *, check_in: date | None = None, check_out: date | None = None, rooms: int = 1, guests: int = 2) -> HotelDetails
async check_availability(hotel_id: str, room_type_id: str, check_in: date, check_out: date, rooms: int = 1) -> AvailabilityResult
```

`compare_hotels` and `get_hotel_policies` are not provider operations. They are derivations for the Phase 2 service layer.

### `search`

1. Reject a currency that differs from the dataset currency with `CurrencyMismatchError`.
2. Validate the date window with `InvalidDateError`.
3. Resolve `destination` case-insensitively against destination_id, city, country and region. No match raises `UnknownDestinationError`.
4. Filter hotels by `guest_rating >= min_rating` and by all required amenities.
5. For each room type with `max_occupancy * rooms >= guests`, build a quote. Drop quotes whose `avg_nightly_rate` is `None` or above `max_nightly_budget`.
6. Choose one quote per hotel by `(not available, avg_nightly_rate, room_type_id)`.
7. Sort hits by `(not available, avg_nightly_rate, hotel_id)`.
8. `matched_amenities` is the sorted intersection of required amenities and hotel amenities.
9. `unmet_preferences` is deterministic: when no hotels match, it contains `no_hotels_matched:<destination>` followed by `filter:max_nightly_budget=<v>`, `filter:min_rating=<v>`, `filter:amenities=<A,B>` for active filters. When hotels match, each free-text preference not found case-insensitively in any hit's name, location, description or amenities becomes `preference_not_verified:<text>`.

### `get_hotel_details`

Raises `UnknownHotelError` for an unknown id. With no dates supplied it uses a single night starting at the dataset anchor date. Returns one quote per room type in dataset order, plus the cancellation policy.

### `check_availability`

Raises `UnknownHotelError` or `UnknownRoomTypeError` for unknown ids. Returns an `AvailabilityResult` built from the same inventory function. A fully or partially sold-out stay is a result with `available=False`, not an exception.

## Error taxonomy

`src/staysmart/domain/errors.py`: `StaySmartError(code, message)` base with a `to_dict()` helper for later HTTP and MCP mapping. Subclasses: `InvalidDateError`, `UnknownDestinationError`, `UnknownHotelError`, `UnknownRoomTypeError`, `CurrencyMismatchError`, `ProviderError`.

Sold-out is a result state, not an exception. A dedicated `SoldOutError` would be dead code in Phase 1 and is deliberately omitted.

`ProviderError` wraps missing files, invalid JSON and pydantic validation failures from the dataset loader with the file path in the message. All errors are logged through `logging.getLogger("staysmart")` with hotel id, destination and date context. No secrets are logged.

## Failure modes to test

1. Missing dataset file.
2. Corrupt or schema-invalid dataset JSON.
3. Unknown destination.
4. Unknown hotel id.
5. Unknown room type id.
6. `check_out <= check_in`.
7. Zero or negative guests.
8. Zero or negative rooms.
9. Dates before the anchor date or beyond the booking window.
10. Stay longer than 30 nights.
11. Non-positive `max_nightly_budget`.
12. `min_rating` outside 0 to 10.
13. Unknown amenity string.
14. Sold-out night from an override.
15. Sold-out night from a destination blackout date.
16. Capacity below requested rooms.
17. Partial availability with no invented total price.
18. Fully sold-out stay with no invented total price.
19. Non-deterministic seed or rate.
20. Currency mismatch between query, settings and dataset.
21. Empty result set that must report unmet filters.
22. Unverifiable free-text preference.

## E2E scenario and expected values

Fixed dates `2026-12-04` to `2026-12-07` (3 nights). December is a peak month (1.10). `2026-12-04` and `2026-12-05` are Friday and Saturday (1.15); `2026-12-06` is Sunday.

`scripts/demo_provider.py` runs four operations and writes `artifacts/provider_demo.json` with `json.dumps(..., indent=2, sort_keys=True)` plus a trailing newline. `tests/phase1/golden/provider_demo.json` is authored from this section, not generated by the implementation.

| Scenario | Input | Expected outcome |
| --- | --- | --- |
| `kyoto_family` | destination Kyoto, budget 250.0, rating 8.0, amenities WIFI and BREAKFAST, preferences `quiet room`, guests 2, rooms 1 | 1 hit: `hotel-kyo-01` / `room-kyo-01-std`, rates `[252.75, 215.82]`, avg `234.28`, total `None`, available `False`, partially available `True`, sold out `2026-12-05`, unmet `preference_not_verified:quiet room` |
| `lisbon_budget` | destination Lisbon, budget 160.0, rating 7.0, amenities WIFI, guests 2, rooms 1 | 2 hits in order: `hotel-lis-01` / `room-lis-01-std` rates `[153.32, 154.84, 149.16]` avg `152.44` total `457.32` available `True`, then `hotel-lis-02` / `room-lis-02-std` rates `[128.35, 85.17]` avg `106.76` total `None` available `False` partially available `True` sold out `2026-12-05` |
| details | `hotel-lis-01`, same dates, rooms 1, guests 2 | Two quotes. Standard fully available as above. Suite rates `[214.61]`, avg `214.61`, total `None`, available `False`, partially available `True`, sold out `2026-12-05` and `2026-12-06`. Policy `free`, refundable `True`, 2 free-cancellation days, 0 penalty nights |
| availability | `hotel-van-03` / `room-van-03-std`, same dates, rooms 1 | 3 nights requested, 0 available, available `False`, sold out `2026-12-04`, `2026-12-05`, `2026-12-06`, empty rates, total `None` |

The E2E test regenerates the artifact, compares it byte-for-byte with the golden, and independently asserts the hotel ids, availability flags, sold-out dates, mock markers and the `quiet room` unverified preference. That makes the snapshot more than a change detector.

## Configuration

`Settings` is a frozen dataclass with `from_env(env=None)`:

| Field | Env var | Default |
| --- | --- | --- |
| `hotel_provider` | `HOTEL_PROVIDER` | `mock` |
| `dataset_path` | `STAYSMART_DATASET_PATH` | `data/hotels/v1/hotels.json` |
| `log_level` | `STAYSMART_LOG_LEVEL` | `INFO` |
| `currency` | `STAYSMART_CURRENCY` | `USD` |
| `window_days` | `STAYSMART_WINDOW_DAYS` | `365` |

`from_env()` loads `.env` only when no explicit `env` mapping is supplied, so tests stay deterministic. An unknown `HOTEL_PROVIDER` value raises `ProviderError`. `configure_logging(level)` configures the `staysmart` logger.
