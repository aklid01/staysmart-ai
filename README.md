# StaySmart AI

An educational MVP demonstrating MCP integration, LLM tool calling, RAG and API development through a hotel discovery and recommendation assistant.

> **Local mock hotel data only.** This project has no connection to Google Hotels or any live hotel inventory. It does not scrape Google Hotels, does not use reverse-engineered endpoints, and does not claim a live Google Hotels integration. It does not implement reservations, payments or booking transactions.

## What is implemented

| Phase | Status |
| --- | --- |
| 0 - Repository foundation, architecture, documentation scaffold | Implemented |
| 1 - Hotel data provider and structured operations | Implemented |
| 2 - Service layer and MCP server with five tools | Implemented |
| 3 - Starlette application service | Not yet implemented |
| 4 - RAG ingestion and retrieval | Not yet implemented |
| 5 - LLM agent orchestration | Not yet implemented |
| 6 - TypeScript frontend | Not yet implemented |
| 7 - Integration testing and final documentation | Not yet implemented |

Documentation describes implemented behavior only. Sections describing future phases are design notes, not available features.

Phase 1 provides:

- Typed pydantic v2 domain models for hotels, room types, cancellation policies, search queries, stay quotes, details, availability and comparison scaffolding.
- A validated `HotelSearchQuery` covering destination, dates, guests, rooms, nightly budget, rating, amenities and free-text preferences.
- A versioned mock dataset with 3 destinations and 10 hotels spanning different ratings, prices, amenities, cancellation policies and availability scenarios.
- A deterministic, date-aware inventory algorithm that derives nightly rates and per-night capacity from a SHA-256 seed, so results never depend on the wall clock.
- An async `HotelProvider` Protocol with three operations: `search`, `get_hotel_details`, `check_availability`.
- Explicit error types, meaningful logging, and honest reporting of sold-out or partially available stays.
- 42 pytest tests plus a reproducible E2E JSON artifact checked against a spec-authored golden file.

Phase 2 adds:

- A service layer deriving `compare_hotels` and `get_hotel_policies` from provider facts through the `HotelProvider` Protocol, with unknown hotel ids reported as `unresolved_hotel_ids` and explicit `information_gaps` for anything the provider does not supply.
- An MCP server built on the official Python SDK 2.x `MCPServer` API exposing exactly five tools over stdio: `search_hotels`, `get_hotel_details`, `check_availability`, `compare_hotels`, `get_hotel_policies`.
- Type-hinted input schemas validated by the SDK, pydantic-model structured outputs, and honest error results: anticipated domain failures surface as `is_error=True` with actionable messages, sold-out stays stay success results, and crashes never leak internals.
- An E2E suite that exercises the server through an in-process MCP client and a real stdio subprocess, plus a deterministic demo artifact checked against a spec-authored golden file (89 tests total across both phases).

## Stack

- Python 3.13, uv, pydantic v2
- Official Python MCP SDK 2.x over local stdio transport, implemented in Phase 2 (`uv run python -m staysmart.mcp_server`)
- Starlette for the HTTP application layer (no FastAPI)
- FastEmbed and a lightweight local vector index for RAG (Phase 4)
- Configurable OpenAI-compatible LLM endpoint (Phase 5)
- TypeScript frontend (Phase 6)
- pytest

No paid API credentials are required for the mock provider, the MCP tools, RAG retrieval or the test suite. A live LLM is optional and configured through environment variables in a later phase.

## Quickstart

```bash
uv python pin 3.13
uv sync
uv run python -c "import staysmart; print('staysmart ok')"
```

Run the MCP server over stdio (it speaks JSON-RPC on stdin/stdout; use an MCP client such as Phase 3's, or `uv run python scripts/demo_mcp.py` for a scripted client session):

```bash
uv run python -m staysmart.mcp_server
```

This machine has several Python 3.13 interpreters and a `pip` that targets a different one than `python`. Always use `uv sync` and `uv run` so commands resolve against the project virtual environment. Never use bare `python` or `pip` for this repository.

Copy `.env.example` to `.env` to override configuration. No secrets are needed at this stage. `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` will be introduced with the agent in Phase 5 and are not read by current code.

No formatter or linter is configured. Adding one requires separate approval.

## Test and demo

```bash
uv run pytest tests/phase1 tests/phase2 -q
uv run python scripts/demo_provider.py
uv run python scripts/demo_mcp.py
```

The provider demo runs a realistic scenario: a Kyoto search with budget, rating and amenity filters; a Lisbon search with a different budget; a details lookup for a hotel with two room types; and an availability check for a fully sold-out stay. It writes a deterministic snapshot to `artifacts/provider_demo.json` (gitignored). `tests/phase1/test_e2e_snapshot.py` regenerates that artifact and compares it with `tests/phase1/golden/provider_demo.json`, which is authored from `tests/phase1/CONTRACT.md` rather than generated by the implementation. Line endings are normalized before comparison because Git may check out CRLF on Windows.

The MCP demo connects an in-process MCP client to the built server and runs the Phase 2 contract scenarios, including a comparison with an unresolved hotel id, two policy lookups and three pinned error cases. It writes `artifacts/mcp_demo.json`, checked against `tests/phase2/golden/mcp_demo.json` by `tests/phase2/test_mcp_e2e_snapshot.py`. Both demos print logging output to stderr and use `Settings()` defaults, so artifacts are pinned to the bundled dataset and unaffected by a local `.env`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOTEL_PROVIDER` | `mock` | Provider implementation selector. Only `mock` exists. |
| `STAYSMART_DATASET_PATH` | bundled `data/hotels/v1/hotels.json` | Override the mock dataset |
| `STAYSMART_LOG_LEVEL` | `INFO` | Python logging level for the `staysmart` logger |
| `STAYSMART_CURRENCY` | `USD` | Expected currency; must match the dataset currency |
| `STAYSMART_WINDOW_DAYS` | `365` | Caps the booking horizon from the dataset anchor date |

Valid booking dates are `[anchor_date, anchor_date + min(dataset.window_days, settings.window_days))`. A stay must be 1 to 30 nights.

## Provider contract

`src/staysmart/providers/base.py` defines the `HotelProvider` Protocol. `MockHotelProvider` is the only implementation. Every returned object carries `data_source="mock"` and `is_live=False`. A partially or fully sold-out stay reports `available=False` and `total_price=None`; it never invents a total. `compare_hotels` and `get_hotel_policies` are service-layer derivations over the Protocol in `src/staysmart/services/`, and the MCP tools in `src/staysmart/mcp_server/` depend only on the Protocol and those services, never on the concrete provider.

The provider behavioral contract, inventory formula, expected values and failure-mode list live in [tests/phase1/CONTRACT.md](tests/phase1/CONTRACT.md). The service and MCP tool contract lives in [tests/phase2/CONTRACT.md](tests/phase2/CONTRACT.md).

## Project layout

```
src/staysmart/config.py                     typed settings and logging setup
src/staysmart/domain/models.py              pydantic v2 contracts
src/staysmart/domain/errors.py              error taxonomy
src/staysmart/providers/base.py             HotelProvider Protocol
src/staysmart/providers/mock/dataset.py     dataset loader and validation
src/staysmart/providers/mock/inventory.py   deterministic date-aware algorithm
src/staysmart/providers/mock/provider.py    MockHotelProvider and factory
src/staysmart/services/comparison.py        compare_hotels derivation
src/staysmart/services/policies.py          get_hotel_policies derivation
src/staysmart/mcp_server/server.py          MCPServer factory
src/staysmart/mcp_server/tools.py           five MCP tools and error mapping
src/staysmart/mcp_server/__main__.py        python -m staysmart.mcp_server stdio entrypoint
data/hotels/v1/hotels.json                  versioned mock dataset
scripts/demo_provider.py                    provider E2E artifact generator
scripts/demo_mcp.py                         MCP E2E artifact generator
tests/phase1/                               provider contract, tests, golden artifact
tests/phase2/                               service and MCP contract, tests, golden artifact
docs/                                       architecture and decision records
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - components, responsibilities and data flow
- [docs/DECISIONS.md](docs/DECISIONS.md) - architectural decisions and rationale
- [docs/MCP.md](docs/MCP.md) - MCP server, tools and schemas
- [docs/API.md](docs/API.md) - HTTP endpoints
- [docs/RAG.md](docs/RAG.md) - ingestion, retrieval and grounding
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) - agent execution and tool calling
