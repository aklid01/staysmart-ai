# MCP server, tools and communication

Status: implemented (Phase 2). Everything below describes behavior that exists in `src/staysmart/mcp_server/` and is covered by `tests/phase2/`.

## Server

`build_mcp_server(settings, provider)` in `src/staysmart/mcp_server/server.py` constructs the official MCP SDK 2.x `MCPServer` (imported from `mcp.server`, package version 2.3.0):

- Name `staysmart-hotels`, version `0.1.0`.
- `instructions` disclose that all data comes from a local mock dataset, every result carries `data_source="mock"` and `is_live=False`, dates are ISO strings, and currency is pinned by the server.
- Logging is configured from `STAYSMART_LOG_LEVEL`; the `staysmart` logger writes to stderr so the stdio protocol channel on stdout stays clean. The stdio E2E test passing is the proof of that separation.

## Transport and entrypoint

The server runs over local stdio:

```bash
uv run python -m staysmart.mcp_server
```

`src/staysmart/mcp_server/__main__.py` builds `Settings.from_env()`, the provider via `get_provider(settings)` (only `mock` exists), the server, and calls `server.run("stdio")`. An unsupported `HOTEL_PROVIDER` fails at startup with a `ProviderError`. MCP communication stays fully separate from any frontend HTTP interface; the Starlette layer (Phase 3) will host its own MCP client and speak to this server over stdio.

## Tools

Five tools, registered in this order. Input schemas derive from type-hinted signatures and are validated by the SDK; dates arrive as ISO strings and coerce to `date`, amenity values must be exact enum members. Output schemas derive from the pydantic return models; clients receive `structured_content` plus text content. No tool accepts a currency argument: the server pins currency from `Settings`, and a settings/dataset mismatch fails at provider construction.

| Tool | Inputs (defaults) | Returns |
| --- | --- | --- |
| `search_hotels` | `destination`, `check_in`, `check_out`, `guests=2`, `rooms=1`, `max_nightly_budget=None`, `min_rating=None`, `amenities=[]`, `preferences=[]` | `HotelSearchResult` |
| `get_hotel_details` | `hotel_id`, `check_in=None`, `check_out=None`, `rooms=1`, `guests=2` | `HotelDetails` |
| `check_availability` | `hotel_id`, `room_type_id`, `check_in`, `check_out`, `rooms=1` | `AvailabilityResult` |
| `compare_hotels` | `hotel_ids` (non-empty), `check_in`, `check_out`, `rooms=1`, `guests=2`, `preferences=[]` | `HotelComparison` |
| `get_hotel_policies` | `hotel_id` | `HotelPolicyInfo` |

Behavior highlights:

- `search_hotels` validates the stay window before building the `HotelSearchQuery`, then delegates to the provider. An empty result set is a success with `total_found=0` and `unmet_preferences` explaining the active filters.
- `get_hotel_details` without dates quotes a single night at the dataset anchor date (`2026-11-01` for the bundled dataset).
- `check_availability` reports sold-out and partially available stays as normal results with `sold_out_dates` and no invented total price.
- `compare_hotels` rejects an empty `hotel_ids` list with the message `hotel_ids must contain at least one hotel id`. Unknown ids are collected in `unresolved_hotel_ids` instead of failing the call; a comparison where every id is unknown is a success with empty `rows`. Rows carry nightly price, total stay price, rating, location, amenities, cancellation policy and availability, derived by `src/staysmart/services/comparison.py` from provider details only.
- `get_hotel_policies` reports grounded policy facts via `src/staysmart/services/policies.py`: the full cancellation policy, a pet policy derived only from the `PET_FRIENDLY` amenity (with a source marker), and explicit `information_gaps` (`check_in_time`, `check_out_time`, plus `pet_policy` when unknown). Nothing is invented.

## Error handling

| Failure | Client-observable result |
| --- | --- |
| Unknown tool name | `is_error=True`, SDK-generated message |
| Schema-invalid arguments (missing required, wrong type, unknown amenity, non-ISO date) | `is_error=True`, SDK validation message |
| Domain failures (`UnknownDestinationError`, `UnknownHotelError`, `UnknownRoomTypeError`, `InvalidDateError`, `CurrencyMismatchError`, `ProviderError`) | `is_error=True`, text `Error executing tool <tool name>: <message>` (the prefix is added by the SDK's tool runner) |
| Sold-out or partial stay | success result, never an error |
| Unexpected provider crash | `is_error=True`, generic `Error executing tool <name>`; internals stay on the server side |

`src/staysmart/mcp_server/tools.py` maps `StaySmartError` to `ToolError` with a small wrapper so anticipated failures keep their actionable message. Example pinned texts:

- `Error executing tool search_hotels: No destination matches 'Atlantis' in the mock dataset`
- `Error executing tool get_hotel_details: Unknown hotel_id 'hotel-xxx-99' in the mock dataset`
- `Error executing tool check_availability: Stay must be between 1 and 30 nights, got -3 from 2026-12-07 to 2026-12-04`
- `Error executing tool search_hotels: check_out must be after check_in`

## Testing and E2E artifact

`tests/phase2/CONTRACT.md` is the behavioral specification; it was written before the implementation and pins schemas, semantics, failure modes and expected values. Three layers exercise the server:

1. `test_mcp_tools.py` calls every tool through an in-process `Client(server=build_mcp_server(...))` (same process, real MCP protocol) and asserts `structured_content` validates against the domain models.
2. `test_mcp_stdio_e2e.py` launches the server as a real subprocess via `StdioServerParameters(command=sys.executable, args=["-m", "staysmart.mcp_server"], cwd=<project root>)`, performs the handshake, lists tools, calls a tool, receives an error result, and shuts down cleanly.
3. `scripts/demo_mcp.py` connects an in-process `Client`, runs the contract scenarios (two searches, details, availability, comparison with an unresolved id, two policy lookups, three error cases) and writes `artifacts/mcp_demo.json` deterministically. `tests/phase2/test_mcp_e2e_snapshot.py` compares it with the spec-authored golden `tests/phase2/golden/mcp_demo.json` (CRLF-normalized) and asserts semantic values independently.

```bash
uv run pytest tests/phase2 -q
uv run python scripts/demo_mcp.py
```

No test requires paid credentials or network access.

## What this server does not do

- It does not expose MCP resources or prompts; tools only, as the brief requires.
- It does not implement reservations, payments or bookings.
- It does not claim live Google Hotels data: every result is marked `data_source="mock"` and `is_live=False`.
