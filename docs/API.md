# HTTP API

Status: implemented (Phase 3). Everything below describes behavior that exists in `src/staysmart/app/` and is covered by `tests/phase3/`.

The Starlette application service accepts frontend requests, validates them against request models that mirror the MCP tool inputs, executes each data operation through exactly one MCP tool call over stdio, and returns the tool payload verbatim. The HTTP layer contains no hotel business logic.

## Running

```bash
uv run python -m staysmart.app
```

The server listens on `STAYSMART_HTTP_HOST:STAYSMART_HTTP_PORT` (default `127.0.0.1:8000`). At startup the app launches the MCP server as a stdio subprocess (`python -m staysmart.mcp_server`) and holds one session for the app lifetime. A failure to establish the session fails startup.

## Endpoints

| Method | Path | Backing MCP tool | Purpose |
| --- | --- | --- | --- |
| GET | `/api/health` | `list_tools` ping | Liveness plus MCP connectivity |
| POST | `/api/search` | `search_hotels` | Structured hotel search |
| GET | `/api/hotels/{hotel_id}` | `get_hotel_details` | Hotel details with room quotes |
| GET | `/api/hotels/{hotel_id}/policies` | `get_hotel_policies` | Grounded policy facts |
| POST | `/api/hotels/{hotel_id}/availability` | `check_availability` | Per-night availability and pricing |
| POST | `/api/compare` | `compare_hotels` | Side-by-side comparison |
| POST | `/api/chat` | none (Phase 3 stub) | Chat entry point reserved for the Phase 5 agent |

Success responses are the MCP tool's structured payload unchanged, including the `data_source="mock"` and `is_live=False` markers on every result.

### GET /api/health

```json
{
  "status": "ok",
  "service": "staysmart-api",
  "version": "0.1.0",
  "provider": "mock",
  "currency": "USD",
  "data_source": "mock",
  "is_live": false,
  "mcp_server": {
    "name": "staysmart-hotels",
    "connected": true,
    "tools": ["check_availability", "compare_hotels", "get_hotel_details", "get_hotel_policies", "search_hotels"]
  }
}
```

When the `list_tools` ping fails the response keeps the same shape with `status: "degraded"`, `mcp_server.connected: false`, `mcp_server.tools: []`, an `error` object with code `mcp_unavailable`, and status code 503.

### POST /api/search

Request body mirrors the `search_hotels` tool inputs. There is no `currency` field; currency is pinned by `STAYSMART_CURRENCY`.

```json
{
  "destination": "Kyoto",
  "check_in": "2026-12-04",
  "check_out": "2026-12-07",
  "guests": 2,
  "rooms": 1,
  "max_nightly_budget": 250.0,
  "min_rating": 8.0,
  "amenities": ["WIFI", "BREAKFAST"],
  "preferences": ["quiet room"]
}
```

Only `destination`, `check_in` and `check_out` are required; omitted optional fields keep their tool defaults. The response is the `HotelSearchResult` payload: `query`, `results` (hotel plus best quote and matched amenities per hit), `total_found`, `unmet_preferences`, and mock markers.

```bash
curl -s -X POST http://127.0.0.1:8000/api/search \
  -H "content-type: application/json" \
  -d '{"destination":"Kyoto","check_in":"2026-12-04","check_out":"2026-12-07","max_nightly_budget":250.0,"min_rating":8.0,"amenities":["WIFI","BREAKFAST"]}'
```

### GET /api/hotels/{hotel_id}

Query parameters: `check_in`, `check_out` (optional ISO dates, default one night at the dataset anchor date `2026-11-01`), `rooms=1`, `guests=2`. Response is the `HotelDetails` payload: hotel facts, per-room-type quotes for the stay dates, and the cancellation policy.

### GET /api/hotels/{hotel_id}/policies

No parameters. Response is the `HotelPolicyInfo` payload: cancellation terms, a pet policy derived only from the amenity list with a provenance marker, and explicit `information_gaps` for anything the provider does not supply (check-in and check-out times are never invented).

### POST /api/hotels/{hotel_id}/availability

```json
{
  "room_type_id": "room-van-03-std",
  "check_in": "2026-12-04",
  "check_out": "2026-12-07",
  "rooms": 1
}
```

Sold-out and partially available stays are 200 responses with `available: false`, `sold_out_dates` and `total_price: null`; they are results, never errors.

### POST /api/compare

```json
{
  "hotel_ids": ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"],
  "check_in": "2026-12-04",
  "check_out": "2026-12-07",
  "rooms": 1,
  "guests": 2,
  "preferences": ["river view"]
}
```

The response is the `HotelComparison` payload: one `row` per resolved hotel with nightly price, total stay price, rating, location, amenities, cancellation policy and availability; unknown ids are listed in `unresolved_hotel_ids` instead of failing the call. An empty `hotel_ids` list is rejected with 400 `empty_hotel_ids`.

### POST /api/chat

```json
{
  "message": "Find a hotel in Kyoto for two guests in December.",
  "conversation_id": "conv-1",
  "history": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
}
```

`message` is required and non-empty; `conversation_id` and `history` are accepted now and will be used by the Phase 5 agent. Phase 3 always responds:

```json
{"error": {"code": "agent_not_available", "message": "The LLM agent is not implemented yet; chat arrives in Phase 5.", "error_type": "AgentNotAvailableError"}}
```

with status 501. No LLM call, conversation storage or tool dispatch happens in Phase 3.

## Error envelope

Every error response uses one envelope:

```json
{"error": {"code": "...", "message": "...", "error_type": "..."}}
```

`details` (a list of `{loc, msg, type}` objects) appears on validation errors only.

| Situation | Status | `code` | Source |
| --- | --- | --- | --- |
| Missing/invalid request fields, unknown amenity, non-positive rooms or guests, unknown query parameters, extra fields | 422 | `validation_error` | Request models (`extra="forbid"`) |
| Malformed or empty JSON body | 400 | `invalid_json` | HTTP layer |
| Unknown destination | 404 | `unknown_destination` | Tool failure classified from message |
| Unknown hotel id | 404 | `unknown_hotel` | Tool failure classified from message |
| Unknown room type id | 404 | `unknown_room_type` | Tool failure classified from message |
| Reversed dates, stay over 30 nights, dates outside the booking window | 400 | `invalid_date` | Tool failure classified from message |
| Empty `hotel_ids` | 400 | `empty_hotel_ids` | Tool failure classified from message |
| Any other tool failure, including provider crashes | 502 | `tool_error` | Classifier fallback |
| MCP session failure mid-request | 503 | `mcp_unavailable` | HTTP layer |
| Unknown route | 404 | `not_found` | HTTP layer |
| Method not allowed | 405 | `method_not_allowed` | HTTP layer |
| Unhandled exception | 500 | `internal_error` | HTTP layer, internals logged not returned |

The `message` for classified tool failures is the raw provider message after stripping the SDK prefix `Error executing tool <name>: `. Semantic date validation stays with the tools (400 via classification), while shape validation happens in the HTTP layer (422).

## CORS

`CORSMiddleware` allows the origins in `STAYSMART_CORS_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`, the Vite dev servers), methods GET and POST, all headers. A preflight from a disallowed origin receives no allow header.

## Testing and E2E artifact

```bash
uv run pytest tests/phase3 -q
uv run python scripts/demo_api.py
```

`tests/phase3/CONTRACT.md` is the behavioral specification, written before the implementation. `scripts/demo_api.py` builds the app with the production stdio connector, launches a real uvicorn server on an ephemeral port, calls every endpoint including the chat stub and six error scenarios, and writes `artifacts/api_demo.json` deterministically (ports and timings excluded). `tests/phase3/test_api_e2e_snapshot.py` byte-compares the artifact with the spec-authored golden `tests/phase3/golden/api_demo.json` after CRLF normalization and asserts the semantic values independently. No test requires paid credentials or network access.
