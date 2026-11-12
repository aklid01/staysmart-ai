# Phase 2 service layer and MCP server contract

This document is the specification for Phase 2. It is written before the service layer and MCP server implementation. Tests and the golden E2E artifact are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 2 delivers a service layer that derives `compare_hotels` and `get_hotel_policies` from provider facts, and an MCP server exposing exactly five tools over stdio: `search_hotels`, `get_hotel_details`, `check_availability`, `compare_hotels`, `get_hotel_policies`. No Starlette app, RAG, agent or frontend exists in this phase. The MCP SDK is 2.3.0 with the v2 API (`MCPServer`, `Client`, `StdioServerParameters`, `ToolError`), verified against the installed package source, not tutorials.

Phase 1 provider behavior is unchanged. Every result object still carries `data_source="mock"` and `is_live=False`. No fact, price or availability value may be invented. Missing information is reported as missing.

## Invariants

- The five tool names are fixed. `list_tools` returns exactly that set.
- Tools accept arguments validated by the SDK from type hints. Anticipated domain failures raise `ToolError` and surface to clients as `CallToolResult` with `is_error=True` whose text is `Error executing tool <tool name>: <StaySmartError message>` (the prefix is added by the SDK's tool runner). Unexpected crashes surface as `is_error=True` with the generic message `Error executing tool <name>`, never with internal details.
- Sold-out and partially available stays are success results, never errors.
- Tools never accept a currency argument. The server pins currency from `Settings`, and a mismatch between settings and dataset fails at provider construction.
- The `staysmart` logger writes to stderr only. The stdio protocol channel on stdout must stay clean; the stdio E2E test passing is the proof.
- Tool definitions depend on the `HotelProvider` Protocol and the service layer, never on `MockHotelProvider` or the dataset directly.
- MCP communication over stdio stays separate from any frontend HTTP interface.

## Domain model extensions (`src/staysmart/domain/models.py`)

`HotelComparison` gains context and honesty fields while keeping its existing `rows` and `unmet_preferences`:

| Field | Type | Meaning |
| --- | --- | --- |
| `rows` | `list[ComparisonRow]` | One row per resolved hotel, in requested order |
| `unresolved_hotel_ids` | `list[str]` | Requested ids not found in the provider, in requested order, deduped |
| `check_in`, `check_out` | `date` | Comparison date range |
| `rooms`, `guests` | `int` | Party used for quotes |
| `currency` | `str` | Currency of all monetary values |
| `unmet_preferences` | `list[str]` | Same `preference_not_verified:<text>` scheme as search |
| `data_source`, `is_live` | `Literal["mock"]`, `Literal[False]` | Mock markers |

`ComparisonRow` is unchanged: `hotel_id`, `name`, `nightly_price`, `total_stay_price`, `guest_rating`, `location`, `amenities` (dataset order), `cancellation_policy` (type string), `refundable`, `availability`.

New `HotelPolicyInfo(StrictModel)`:

| Field | Type | Meaning |
| --- | --- | --- |
| `hotel_id`, `hotel_name`, `general_info` | `str` | Id, name, provider description |
| `cancellation_policy` | `CancellationPolicy` | Full policy object from provider facts |
| `pet_policy` | `str` | `"allowed"` when `PET_FRIENDLY` is a hotel amenity, otherwise `"unknown"` |
| `pet_policy_source` | `Literal["amenities", "not_provided"]` | Provenance of `pet_policy` |
| `check_in_time`, `check_out_time` | `str | None` | Always `None` in this dataset; never invented |
| `information_gaps` | `list[str]` | Deterministic order: `check_in_time`, `check_out_time`, plus `pet_policy` when unknown |
| `data_source`, `is_live` | mock markers | |

## Service layer (`src/staysmart/services/`)

`src/staysmart/services/comparison.py`:

```
async compare_hotels(provider, *, hotel_ids, check_in, check_out, rooms=1, guests=2, preferences=()) -> HotelComparison
```

1. Stay length is validated eagerly (1 to 30 nights, `check_out` after `check_in`) and raises `InvalidDateError`, even when every id is unknown. The booking-window check happens inside provider details calls.
2. Ids are deduped preserving first-occurrence order.
3. Each id resolves through `provider.get_hotel_details(id, check_in=..., check_out=..., rooms=..., guests=...)`. `UnknownHotelError` moves the id to `unresolved_hotel_ids` and never fails the call.
4. Per row:
   - `nightly_price` = lowest `avg_nightly_rate` among the hotel's room quotes with at least one available night; `None` when every night of every room is sold out.
   - `total_stay_price` = lowest `total_price` among fully available room quotes; `None` when no room is fully available.
   - `availability` = `True` when any room quote is fully available.
   - `guest_rating`, `location`, `amenities`, `cancellation_policy` type and `refundable` come straight from provider facts.
5. `unmet_preferences` uses the search scheme: each free-text preference not found case-insensitively in any resolved hotel's name, location, description or amenities becomes `preference_not_verified:<text>`.
6. All ids unresolved yields a success result with `rows=[]`; it is not an error.

`src/staysmart/services/policies.py`:

```
async get_hotel_policies(provider, hotel_id) -> HotelPolicyInfo
```

Fetches details with default dates (unused for policy facts). `UnknownHotelError` propagates. Pet policy is derived only from the amenity list; check-in and check-out times are never invented and always appear in `information_gaps`.

## MCP server (`src/staysmart/mcp_server/`)

`src/staysmart/mcp_server/server.py` exposes `build_mcp_server(settings, provider) -> MCPServer` named `staysmart-hotels`, version `0.1.0`, with honest instructions stating the data is a local mock dataset and all results carry mock markers. Tools are registered in this order: `search_hotels`, `get_hotel_details`, `check_availability`, `compare_hotels`, `get_hotel_policies`.

`src/staysmart/mcp_server/__main__.py` is the stdio entrypoint: `python -m staysmart.mcp_server` builds `Settings.from_env()`, the provider via `get_provider`, the server, and calls `server.run("stdio")`.

## Tool schemas

Input schemas derive from type-hinted signatures validated by the SDK. Output schemas derive from the pydantic return models; clients receive `structured_content` plus text content.

| Tool | Inputs | Returns |
| --- | --- | --- |
| `search_hotels` | `destination: str`, `check_in: date`, `check_out: date`, `guests: int = 2`, `rooms: int = 1`, `max_nightly_budget: float | None = None`, `min_rating: float | None = None`, `amenities: list[Amenity] = []`, `preferences: list[str] = []` | `HotelSearchResult` |
| `get_hotel_details` | `hotel_id: str`, `check_in: date | None = None`, `check_out: date | None = None`, `rooms: int = 1`, `guests: int = 2` | `HotelDetails` |
| `check_availability` | `hotel_id: str`, `room_type_id: str`, `check_in: date`, `check_out: date`, `rooms: int = 1` | `AvailabilityResult` |
| `compare_hotels` | `hotel_ids: list[str]`, `check_in: date`, `check_out: date`, `rooms: int = 1`, `guests: int = 2`, `preferences: list[str] = []` | `HotelComparison` |
| `get_hotel_policies` | `hotel_id: str` | `HotelPolicyInfo` |

Dates are ISO strings on the wire and coerce to `date`. Amenity values must be exact enum values (`WIFI`, `POOL`, `GYM`, `BREAKFAST`, `PARKING`, `SPA`, `PET_FRIENDLY`, `AIR_CONDITIONING`, `RESTAURANT`, `SHUTTLE`). `compare_hotels` rejects an empty `hotel_ids` list at the tool boundary with `ToolError` and message `hotel_ids must contain at least one hotel id`.

## Error handling contract

| Failure | Surface |
| --- | --- |
| Unknown tool name | `is_error=True`, SDK-generated message |
| Schema-invalid arguments (wrong type, unknown amenity, missing required, non-ISO date) | `is_error=True`, SDK validation message |
| Unknown destination, unknown hotel, unknown room type, invalid date order, stay beyond 30 nights, dates outside the booking window, provider data failures | `is_error=True` whose text is `Error executing tool <tool name>: <StaySmartError message>` |
| Sold-out or partial stay | success result with `available=False`, sold-out dates, and no invented total |
| Empty comparison result set | success with `rows=[]` and `unresolved_hotel_ids` |
| Provider crash (`RuntimeError` and friends) | `is_error=True` with generic `Error executing tool <name>` |

Expected provider messages, pinned for tests and the artifact. They arrive after the `Error executing tool <tool name>: ` prefix:

- `No destination matches 'Atlantis' in the mock dataset`
- `Unknown hotel_id 'hotel-xxx-99' in the mock dataset`
- `Stay must be between 1 and 30 nights, got -3 from 2026-12-07 to 2026-12-04` (`check_availability`; the provider window check runs first there)
- `check_out must be after check_in` (`search_hotels` and `compare_hotels`, whose stay-length validation runs before the provider window check)
- `Unknown room_type_id 'room-lis-02-suite' for hotel 'hotel-lis-02'`

## Failure modes to test

1. Unknown tool name called.
2. Missing required argument.
3. Unknown amenity value.
4. Non-ISO date string.
5. `check_out <= check_in` per tool.
6. Stay longer than 30 nights.
7. Dates before the anchor date or beyond the booking window.
8. Unknown destination.
9. Unknown hotel id.
10. Unknown room type id.
11. Sold-out stay reported as a success result.
12. Partial availability with no invented total price.
13. Empty search result set as a success.
14. Comparison with unknown ids reporting `unresolved_hotel_ids`.
15. Comparison with duplicate ids deduped.
16. Comparison with every id unresolved as a success with empty rows.
17. Empty `hotel_ids` rejected at the tool boundary.
18. Comparison date validation firing even when all ids are unknown.
19. Pet policy honesty for hotels with and without `PET_FRIENDLY`.
20. Currency pinned from settings, absent from tool inputs.
21. Unexpected provider crash returning the generic error message.
22. stdio transport: handshake, tool listing, call, error result, clean shutdown.
23. Default-dates details call landing on the dataset anchor single night.

## E2E demo artifact

`scripts/demo_mcp.py` connects an in-process `Client` to the built server, runs the scenarios below, and writes `artifacts/mcp_demo.json` with `json.dumps(..., indent=2, sort_keys=True)` plus a trailing newline. Values come from result objects, serialized with ISO dates. `tests/phase2/golden/mcp_demo.json` is authored from this section, not generated by the implementation.

Top-level keys: `artifact_version: 1`, `server_name: "staysmart-hotels"`, `transport: "in-process"`, `currency: "USD"`, `data_source: "mock"`, `is_live: false`, `dataset_schema_version: 1`, `tools_listed` (sorted five names), `results`, `errors`.

`results` keys and inputs (all dates 2026-12-04 to 2026-12-07, rooms 1, guests 2 unless stated):

| Key | Operation | Inputs |
| --- | --- | --- |
| `search_kyoto_family` | `search_hotels` | Kyoto, budget 250.0, rating 8.0, amenities WIFI+BREAKFAST, preferences `quiet room` |
| `search_lisbon_budget` | `search_hotels` | Lisbon, budget 160.0, rating 7.0, amenities WIFI |
| `details_lis_01` | `get_hotel_details` | `hotel-lis-01` |
| `availability_van_03` | `check_availability` | `hotel-van-03` / `room-van-03-std` |
| `compare_lisbon` | `compare_hotels` | ids `hotel-lis-01`, `hotel-lis-02`, `hotel-xxx-99`, preferences `river view` |
| `policies_kyo_01` | `get_hotel_policies` | `hotel-kyo-01` |
| `policies_lis_01` | `get_hotel_policies` | `hotel-lis-01` |

Search and details summaries reuse the Phase 1 golden values verbatim (same dataset, same dates): Kyoto family yields one hit `hotel-kyo-01` / `room-kyo-01-std` with rates `[252.75, 215.82]`, avg `234.28`, sold out `2026-12-05`, unmet `preference_not_verified:quiet room`. Lisbon budget yields `hotel-lis-01` / `room-lis-01-std` (avg `152.44`, total `457.32`, available) then `hotel-lis-02` / `room-lis-02-std` (avg `106.76`, total `None`, sold out `2026-12-05`). Details lists the two `hotel-lis-01` room quotes with policy `free`, refundable, 2 free days, 0 penalty nights. Availability reports 3 nights requested, 0 available, sold out on all three dates, total `None`.

`compare_lisbon` summary: `hotel_ids_requested: ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"]`, `unresolved_hotel_ids: ["hotel-xxx-99"]`, `unmet_preferences: ["preference_not_verified:river view"]`, currency USD, rooms 1, guests 2, and rows in requested order:

| Row | nightly_price | total_stay_price | guest_rating | availability | policy |
| --- | --- | --- | --- | --- | --- |
| `hotel-lis-01` Alfama Riverside Boutique, Alfama, Lisbon | 152.44 | 457.32 | 8.7 | true | free, refundable |
| `hotel-lis-02` Baixa Central Hotel, Baixa, Lisbon | 106.76 | null | 7.9 | false | flexible, refundable |

`hotel-lis-01` nightly price is the minimum across its standard (152.44) and suite (214.61) quotes; the suite is partially available so only the standard room supplies a total.

`policies_kyo_01`: pet policy `allowed` with source `amenities`; policy `partial`, refundable, 5 free-cancellation days, 1 penalty night; `information_gaps: ["check_in_time", "check_out_time"]`. `policies_lis_01`: pet policy `unknown` with source `not_provided`; policy `free`, refundable, 2 days, 0 penalty; `information_gaps: ["check_in_time", "check_out_time", "pet_policy"]`.

`errors` records, each `{"is_error": true, "message": "<pinned message>"}`:

| Key | Operation | Inputs |
| --- | --- | --- |
| `unknown_destination_search` | `search_hotels` | destination `Atlantis`, valid dates |
| `unknown_hotel_details` | `get_hotel_details` | `hotel-xxx-99` |
| `invalid_dates_availability` | `check_availability` | `hotel-lis-02` / `room-lis-02-std`, check_in 2026-12-07, check_out 2026-12-04 |

## Testing approach

`tests/phase2/conftest.py` provides settings, provider, and an in-process `Client(server=build_mcp_server(...))` fixture. `test_comparison_service.py` and `test_policies_service.py` test the derivations directly. `test_mcp_tools.py` exercises every tool through the MCP client, never by calling tool functions directly, and asserts `structured_content` validates against the domain models. `test_mcp_stdio_e2e.py` launches `python -m staysmart.mcp_server` via `StdioServerParameters(command=sys.executable, ...)` with `cwd` at the project root, performs a handshake, lists tools, calls a tool, receives an error result, and shuts down cleanly. `test_e2e_snapshot.py` regenerates the artifact and compares it with the golden after CRLF normalization, plus independent semantic assertions. No test requires paid credentials or network access.
