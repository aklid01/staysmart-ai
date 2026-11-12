# Phase 3 Starlette application service and MCP client contract

This document is the specification for Phase 3. It is written before the application implementation. Tests and the golden E2E artifact are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 3 delivers the HTTP application layer: a Starlette app in `src/staysmart/app/` that hosts an MCP client connected to the Phase 2 `staysmart-hotels` server over stdio, exposes structured hotel endpoints plus health and a chat stub, and prepares the seam where the Phase 5 LLM agent plugs in. No agent orchestration, RAG, or frontend exists in this phase. Starlette and uvicorn are already declared dependencies; `httpx` joins the dev group for `TestClient`.

Phase 1 and Phase 2 behavior is unchanged. The HTTP layer adds no hotel business logic: every data operation goes through an MCP tool call, and success responses return the tool payload unchanged.

## Invariants

- Every data endpoint obtains its response from exactly one MCP tool call. The HTTP layer does not import the provider, the dataset, or the service layer.
- Success responses return the tool's structured payload verbatim, preserving `data_source="mock"` and `is_live=False` markers.
- The production connector launches the MCP server as a stdio subprocess (`python -m staysmart.mcp_server`, cwd at the project root) and keeps one long-lived session for the app lifetime, entered and exited inside the Starlette lifespan.
- The connector is injectable. Tests use an in-process connector wrapping `build_mcp_server(...)`; one transport test and the demo artifact exercise the real stdio subprocess.
- The `staysmart` logger keeps writing to stderr only; uvicorn logs also go to stderr. The stdio protocol channel on stdout stays clean.
- Currency never appears in any request schema; it is pinned by `Settings` inside the tools.
- POST `/api/chat` is a stub: the request schema is validated, but the response is always 501 `agent_not_available`. No LLM call, no conversation storage, no tool dispatch happens in Phase 3.

## Configuration additions (`src/staysmart/config.py`, `.env.example`)

| Setting | Env var | Default | Validation |
| --- | --- | --- | --- |
| `http_host` | `STAYSMART_HTTP_HOST` | `127.0.0.1` | none |
| `http_port` | `STAYSMART_HTTP_PORT` | `8000` | integer, 1 to 65535 |
| `cors_origins` | `STAYSMART_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | comma-separated, whitespace stripped, empty entries dropped |

Invalid values raise `ProviderError` like the existing settings. `cors_origins` is stored as an immutable tuple.

## Modules (`src/staysmart/app/`)

- `mcp_client.py` - connector seam. `McpSession` protocol exposes `list_tools() -> list[str]` (sorted tool names) and `call_tool(name, arguments) -> dict` (structured payload). `McpConnector` protocol exposes `connect()` returning an async context manager yielding an `McpSession`. `StdioMcpConnector` (production) builds `StdioServerParameters(command=sys.executable, args=["-m", "staysmart.mcp_server"], cwd=PROJECT_ROOT)` with `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, and `STAYSMART_LOG_LEVEL` carried from settings. `InProcessMcpConnector` wraps an existing `MCPServer` instance for tests and demos. A session `call_tool` raises `ToolFailureError(message)` when the result `is_error` flag is set; the SDK prefix `Error executing tool <tool name>: ` is stripped before classification. Transport-level exceptions propagate to the route layer.
- `errors.py` - `ApiError(status, code, message, error_type, details=None)` plus the handlers installed on the app. All error responses share one envelope: `{"error": {"code", "message", "error_type"}}` with an optional `details` list for validation errors. `classify_tool_failure(message)` maps provider message fragments to statuses (table below). Malformed JSON body -> 400 `invalid_json`. Pydantic request validation failure -> 422 `validation_error` with `details` limited to `loc`, `msg`, `type`. `StarletteHTTPException` -> 404 `not_found` for unknown routes, 405 `method_not_allowed` otherwise. Unhandled exceptions -> 500 `internal_error` without internals, logged via `logger.exception`.
- `routes.py` - request models and endpoint handlers. Request models are pydantic models with `extra="forbid"` mirroring tool inputs 1:1, plus positivity constraints (`ge=1`) on `guests` and `rooms` that the tool schemas leave open. POST bodies parse via `await request.body()`, `json.loads`, `model_validate`; query parameters parse through a pydantic model over `request.query_params`.
- `main.py` - `create_app(settings, connector=None)`: builds the Starlette app, stores the connector on `app.state`, wires the lifespan (enter `connector.connect()`, publish the session as `app.state.mcp`, exit on shutdown), installs CORS middleware (`allow_origins` from settings, methods GET and POST, all headers), registers routes and error handlers. `APP_VERSION` resolves from installed package metadata with a `0.0.0` fallback.
- `__main__.py` - entrypoint `python -m staysmart.app`: `Settings.from_env()`, `configure_logging`, `create_app`, `uvicorn.run(app, host, port, log_level)`.

## Endpoints

| Method | Path | Tool | Request | Success |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | `list_tools` ping | none | 200 body below |
| POST | `/api/search` | `search_hotels` | `SearchRequest` | 200 `HotelSearchResult` payload |
| GET | `/api/hotels/{hotel_id}` | `get_hotel_details` | `DetailsQuery` params | 200 `HotelDetails` payload |
| GET | `/api/hotels/{hotel_id}/policies` | `get_hotel_policies` | none | 200 `HotelPolicyInfo` payload |
| POST | `/api/hotels/{hotel_id}/availability` | `check_availability` | `AvailabilityRequest` | 200 `AvailabilityResult` payload |
| POST | `/api/compare` | `compare_hotels` | `CompareRequest` | 200 `HotelComparison` payload |
| POST | `/api/chat` | none (stub) | `ChatRequest` | 501 `agent_not_available` |

Request models:

- `SearchRequest`: `destination` (min_length 1), `check_in`, `check_out` (ISO dates), `guests=2`, `rooms=1` (both `ge=1`), `max_nightly_budget: float | None`, `min_rating: float | None`, `amenities: list[Amenity] = []`, `preferences: list[str] = []`.
- `DetailsQuery`: `check_in: date | None`, `check_out: date | None`, `rooms=1`, `guests=2` (both `ge=1`).
- `AvailabilityRequest`: `room_type_id` (min_length 1), `check_in`, `check_out`, `rooms=1` (`ge=1`).
- `CompareRequest`: `hotel_ids: list[str]` (no minimum, mirroring the tool so the tool boundary rejects empty lists), `check_in`, `check_out`, `rooms=1`, `guests=2` (both `ge=1`), `preferences: list[str] = []`.
- `ChatRequest`: `message` (min_length 1), `conversation_id: str | None = None`, `history: list[ChatMessage] = []` where `ChatMessage` is `role: Literal["user", "assistant"]` plus `content` (min_length 1).

Health body (200):

```json
{
  "status": "ok",
  "service": "staysmart-api",
  "version": "0.1.0",
  "provider": "mock",
  "currency": "USD",
  "data_source": "mock",
  "is_live": false,
  "mcp_server": {"name": "staysmart-hotels", "connected": true, "tools": ["check_availability", "compare_hotels", "get_hotel_details", "get_hotel_policies", "search_hotels"]}
}
```

When the `list_tools` ping fails, health returns 503 with `status: "degraded"`, `connected: false`, `tools: []`, and an `error` object `{"code": "mcp_unavailable", "message": "<exception type name> while listing MCP tools", "error_type": "McpUnavailableError"}`. The degraded test injects a connector whose session always raises, so the message is deterministic.

Chat stub body (501), with the same envelope as other errors:

```json
{"error": {"code": "agent_not_available", "message": "The LLM agent is not implemented yet; chat arrives in Phase 5.", "error_type": "AgentNotAvailableError"}}
```

CORS: a preflight `OPTIONS` request from an allowed origin returns the origin in `access-control-allow-origin`; a disallowed origin gets no allow header.

## Error mapping

Tool failures carry the raw message after prefix stripping. `classify_tool_failure` matches fragments case-sensitively, first match wins, fallback to 502:

| Fragment | Status | `code` | `error_type` |
| --- | --- | --- | --- |
| `No destination matches` | 404 | `unknown_destination` | `UnknownDestinationError` |
| `Unknown hotel_id` | 404 | `unknown_hotel` | `UnknownHotelError` |
| `Unknown room_type_id` | 404 | `unknown_room_type` | `UnknownRoomTypeError` |
| `hotel_ids must contain at least one hotel id` | 400 | `empty_hotel_ids` | `ToolError` |
| `check_out must be after check_in` | 400 | `invalid_date` | `InvalidDateError` |
| `Stay must be between 1 and` | 400 | `invalid_date` | `InvalidDateError` |
| `stay length must be between 1 and` | 400 | `invalid_date` | `InvalidDateError` |
| `outside the mock dataset window` | 400 | `invalid_date` | `InvalidDateError` |
| any other tool failure (including the generic crash message `Error executing tool <name>` with no suffix) | 502 | `tool_error` | `ToolError` |

`message` is the raw tool text after prefix stripping (no rewording). A provider crash exercised through an exploding provider surfaces as 502 with message `Error executing tool search_hotels`. Any exception escaping a `call_tool` other than a tool failure (subprocess death, connection loss) becomes 503 `mcp_unavailable` with `error_type` `McpUnavailableError` and the exception type name in the message.

Semantic validation stays with the tools: date order, stay length, and booking-window failures are 400 from the classifier, not 422 from the HTTP layer. Shape validation (missing fields, wrong types, unknown amenity values, non-positive rooms or guests, unknown query parameters) is 422 from the request models.

## Failure modes to test

1. Health reports ok with the five sorted tool names and connected true.
2. Health reports degraded 503 when the session ping fails.
3. Search happy path (Kyoto) with pinned values and mock markers.
4. Search budget path (Lisbon) with pinned values.
5. Unknown destination -> 404 `unknown_destination`.
6. Reversed dates -> 400 `invalid_date` with the exact provider message.
7. Stay beyond 30 nights -> 400 `invalid_date`.
8. Missing required field -> 422 `validation_error` with details.
9. Unknown amenity value -> 422.
10. Non-positive rooms or guests -> 422.
11. Malformed JSON body -> 400 `invalid_json`.
12. Unknown route -> 404 `not_found`.
13. Details happy path with pinned quotes; unknown hotel -> 404.
14. Details default dates land on the dataset anchor single night (`2026-11-01` to `2026-11-02`).
15. Availability happy path (sold-out scenario) as a 200 success; unknown room type -> 404.
16. Compare happy path with unresolved ids; empty `hotel_ids` -> 400 `empty_hotel_ids`.
17. Policies happy paths for a pet-friendly and a non-pet-friendly hotel.
18. Chat valid body -> 501 `agent_not_available`; empty message -> 422.
19. Provider crash -> 502 `tool_error` with the generic message.
20. Session failure mid-request -> 503 `mcp_unavailable`.
21. CORS preflight allowed and disallowed origins.
22. stdio transport: health and search through the real subprocess app.
23. E2E artifact regenerated by the demo script matches the golden after CRLF normalization.

## E2E demo artifact

`scripts/demo_api.py` builds the app with the production stdio connector, launches it on a real uvicorn server bound to an ephemeral port on `127.0.0.1`, runs the scenarios below over HTTP with `httpx`, and writes `artifacts/api_demo.json` with `json.dumps(..., indent=2, sort_keys=True)` plus a trailing newline. Recorded values come from response bodies, summarized with ISO dates; port numbers and durations are excluded so the artifact is deterministic. `tests/phase3/golden/api_demo.json` is authored from this section, not generated by the implementation.

Top-level keys: `artifact_version: 1`, `service: "staysmart-api"`, `server_name: "staysmart-hotels"`, `transport: "stdio"`, `currency: "USD"`, `data_source: "mock"`, `is_live: false`, `base_url: "http://127.0.0.1"`, `requests`, `errors`.

`requests` keys and inputs (dates 2026-12-04 to 2026-12-07, rooms 1, guests 2 unless stated). Each record is `{"method", "path", "status", "body"}` where `body` is the full response for health and chat and a summary for the large payloads:

| Key | Request | Inputs |
| --- | --- | --- |
| `health` | `GET /api/health` | none |
| `search_kyoto_family` | `POST /api/search` | Kyoto, budget 250.0, rating 8.0, amenities WIFI+BREAKFAST, preferences `quiet room` |
| `search_lisbon_budget` | `POST /api/search` | Lisbon, budget 160.0, rating 7.0, amenities WIFI |
| `details_lis_01` | `GET /api/hotels/hotel-lis-01` | check_in, check_out, rooms, guests query params |
| `availability_van_03` | `POST /api/hotels/hotel-van-03/availability` | `room-van-03-std`, dates, rooms 1 |
| `compare_lisbon` | `POST /api/compare` | ids `hotel-lis-01`, `hotel-lis-02`, `hotel-xxx-99`, preferences `river view` |
| `policies_kyo_01` | `GET /api/hotels/hotel-kyo-01/policies` | none |
| `policies_lis_01` | `GET /api/hotels/hotel-lis-01/policies` | none |
| `chat_stub` | `POST /api/chat` | message `Find a hotel in Kyoto for two guests in December.` |

Search and details summaries reuse the Phase 2 golden values verbatim (same dataset, same dates): Kyoto family yields one hit `hotel-kyo-01` / `room-kyo-01-std` with rates `[252.75, 215.82]`, avg `234.28`, nights available 2, sold out `2026-12-05`, unmet `preference_not_verified:quiet room`. Lisbon budget yields `hotel-lis-01` / `room-lis-01-std` (avg `152.44`, total `457.32`, available) then `hotel-lis-02` / `room-lis-02-std` (avg `106.76`, rates `[128.35, 85.17]`, total `None`, sold out `2026-12-05`). Details lists the two `hotel-lis-01` room quotes (standard `[153.32, 154.84, 149.16]` total `457.32`; suite avg `214.61`, nights available 1, sold out `2026-12-05` and `2026-12-06`) with policy `free`, refundable, 2 free days, 0 penalty nights. Availability reports 3 nights requested, 0 available, sold out on `2026-12-04`, `2026-12-05`, `2026-12-06`, empty nightly rates, total `None`.

`compare_lisbon` summary: rows in requested order with `hotel-lis-01` (nightly `152.44`, total `457.32`, rating 8.7, available) and `hotel-lis-02` (nightly `106.76`, total `None`, rating 7.9, unavailable), `unresolved_hotel_ids: ["hotel-xxx-99"]`, `unmet_preferences: ["preference_not_verified:river view"]`.

`policies_kyo_01`: pet `allowed` / `amenities`, policy `partial`, refundable, 5 days, 1 penalty night. `policies_lis_01`: pet `unknown` / `not_provided`, policy `free`, refundable, 2 days, 0 penalty nights, gaps include `pet_policy`.

`chat_stub` record: status 501 with the `agent_not_available` envelope.

`errors` records, each `{"method", "path", "status", "body": {"error": {...}}}`:

| Key | Request | Inputs | Status |
| --- | --- | --- | --- |
| `unknown_destination_search` | `POST /api/search` | destination `Atlantis`, valid dates | 404 |
| `unknown_hotel_details` | `GET /api/hotels/hotel-xxx-99` | none | 404 |
| `invalid_dates_availability` | `POST /api/hotels/hotel-lis-02/availability` | `room-lis-02-std`, check_in `2026-12-07`, check_out `2026-12-04` | 400 |
| `empty_compare_hotel_ids` | `POST /api/compare` | `hotel_ids: []`, valid dates | 400 |
| `validation_missing_destination` | `POST /api/search` | dates only | 422 |
| `chat_empty_message` | `POST /api/chat` | `message: ""` | 422 |

## Testing approach

`tests/phase3/conftest.py` provides settings (including the new HTTP fields), provider, MCP server, an app built with `InProcessMcpConnector`, and a `TestClient` entered as a context manager so the lifespan runs. Endpoint tests assert status codes, error envelopes, and pinned payload values, and validate success bodies against the domain pydantic models. `test_api_transport.py` builds the app with `StdioMcpConnector` and proves health and search over the real stdio subprocess. A failing-session connector proves the degraded health and `mcp_unavailable` paths; an exploding provider proves the 502 `tool_error` fallback. `test_api_e2e_snapshot.py` runs `scripts/demo_api.py` as a subprocess, byte-compares `artifacts/api_demo.json` with the golden after CRLF normalization, and adds independent semantic assertions. No test requires paid credentials or network access.
