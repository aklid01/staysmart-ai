# StaySmart AI

An educational MVP demonstrating MCP integration, LLM tool calling, RAG and API development through a hotel discovery and recommendation assistant.

> **Local mock hotel data only.** This project has no connection to Google Hotels or any live hotel inventory. It does not scrape Google Hotels, does not use reverse-engineered endpoints, and does not claim a live Google Hotels integration. It does not implement reservations, payments or booking transactions.

## What is implemented

| Phase | Status |
| --- | --- |
| 0 - Repository foundation, architecture, documentation scaffold | Implemented |
| 1 - Hotel data provider and structured operations | Implemented |
| 2 - Service layer and MCP server with five tools | Implemented |
| 3 - Starlette application service and MCP client integration | Implemented |
| 4 - RAG ingestion and retrieval | Implemented |
| 5 - LLM agent orchestration | Implemented |
| 6 - TypeScript frontend | Implemented |
| 7 - Integration testing and final documentation | Implemented |

Documentation describes implemented behavior only.

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

Phase 3 adds:

- A Starlette application service (`uv run python -m staysmart.app`) exposing `GET /api/health`, structured hotel endpoints (`/api/search`, `/api/hotels/{id}`, `/api/hotels/{id}/policies`, `/api/hotels/{id}/availability`, `/api/compare`) and a validated 501 `/api/chat` stub reserved for the Phase 5 agent.
- An MCP client seam in the app: the production connector launches the MCP server as a stdio subprocess and holds one long-lived session for the app lifetime; tests inject an in-process connector. `/api/health` pings the session and reports the five tools.
- Request models mirroring the tool inputs (`extra="forbid"`, positive guests and rooms), a single `{"error": {...}}` envelope, and a classifier mapping tool failures to 404/400/502 while MCP session failures become 503.
- CORS middleware with configurable origins for the future frontend, and an E2E suite (33 tests) including a real uvicorn server artifact checked against a spec-authored golden file (122 tests total across phases 1-3).

Phase 4 adds:

- An authored knowledge corpus of 53 markdown documents in `data/knowledge/v1/` (general info, rooms, amenities, cancellation and pet policies per hotel, plus destination check-in/check-out guides), fact-pinned to the mock dataset by consistency tests and guaranteed free of prices and availability claims.
- A RAG stack in `src/staysmart/rag/`: frontmatter validation, heading-based chunking (600-char limit), FastEmbed embeddings (`BAAI/bge-small-en-v1.5`, 384 dims), a local numpy cosine vector index persisted to `data/rag/index` (gitignored), and `python -m staysmart.rag ingest` to build it.
- A `RagRetriever` service with metadata filters (hotel, destination, category), semantic ranking, and context construction with per-document source attribution, ready for the Phase 5 agent to combine with structured hotel data.
- An offline test path via a deterministic stub embedder plus a real-model E2E snapshot (42 tests in phase 4; 164 total). The FastEmbed model is a free one-time download; no paid credentials anywhere.

Phase 5 adds:

- An LLM agent in `src/staysmart/agent/` wired to `POST /api/chat`: it plans tool calls over the five MCP tools plus a `search_knowledge` knowledge tool, executes them over the app's stdio MCP session and the Phase 4 retriever, and answers with grounded text, tool-derived hotel payloads, knowledge sources and a tool trace.
- Structural safeguards: at most 6 model turns and 12 tool calls per chat with forced no-tool summaries, exact-duplicate call rejection, tool errors fed back to the model, and hotel cards assembled exclusively from real tool payloads so fabricated hotels cannot reach the frontend.
- Model configuration through `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` (OpenAI-compatible endpoints; the default targets the local endpoint and needs no key). Agent logic tests run offline against a scripted model; the real-model E2E skips when the endpoint is unreachable.
- 181 tests total across phases 1-5, including endpoint contract tests for the new chat behavior (200 structured response, 503 `llm_unavailable`, 503 `rag_unavailable`).

Phase 6 adds:

- A chat-first hotel discovery UI in `frontend/` (Vite + React + TypeScript, no router, no state library, plain CSS): chat thread with markdown-lite rendering, hotel cards built from the agent's tool payloads, comparison tables, source and tool-trace chips, and typing/error states.
- Hotel cards show destination gradient placeholders (no binary images), star and guest ratings, nightly and total prices, amenity chips, cancellation badges, availability with sold-out dates, and a persistent `mock data` badge.
- Details and policies dialogs call the structured endpoints (`/api/hotels/{id}` with the stay dates, `/api/hotels/{id}/policies`), rendering room quotes, cancellation terms, pet policy with its source marker and explicit information-gap chips.
- The header shows a live `/api/health` status dot. Errors render from the API error envelope; a stopped backend shows a readable banner while the thread keeps the user's message for retry.
- Browser E2E verified black-box with screenshots and an interaction log (`tests/phase6/interaction_log.json`, screenshots under `artifacts/ui_demo/`).

Phase 7 adds:

- A cross-layer integration suite (`tests/phase7/`): one full journey from health through chat (search plus knowledge tool calls) to the structured endpoints with cross-layer consistency checks, documentation drift guards (routes vs `docs/API.md`, env vars vs README and `.env.example`, quickstart commands vs real files), and an artifact sweep that regenerates every demo artifact from current code and verifies mock markers.
- Reliability polish: the agent system prompt now requires quoting check-in/check-out times from retrieved destination guides (fixing the conservative-answer variance observed in Phase 5), the frontend linter passes with zero warnings, and known limitations (MCP session recovery requires a service restart) are documented in the decision record.
- The MVP is feature-complete: all phases 0-7 implemented, 190+ tests green across the suite, every Definition of Done criterion verified by an automated test or a committed artifact.

## Stack

- Python 3.13, uv, pydantic v2
- Official Python MCP SDK 2.x over local stdio transport, implemented in Phase 2 (`uv run python -m staysmart.mcp_server`)
- Starlette for the HTTP application layer, implemented in Phase 3 (`uv run python -m staysmart.app`)
- FastEmbed (`BAAI/bge-small-en-v1.5`) with a local numpy vector index for RAG, implemented in Phase 4 (`uv run python -m staysmart.rag ingest`)
- OpenAI-compatible LLM agent, implemented in Phase 5 (default target `http://127.0.0.1:3425/v1`, no key needed)
- TypeScript frontend (Phase 6)
- pytest

No paid API credentials are required for the mock provider, the MCP tools, RAG retrieval, the agent logic tests or the test suite. The FastEmbed model downloads once (free, roughly 0.1 GB) on the first RAG ingestion or demo run and is cached locally afterwards. Live chat answers need a reachable LLM endpoint; every other feature runs fully offline.

## Quickstart

```bash
uv python pin 3.13
uv sync
uv run python -c "import staysmart; print('staysmart ok')"
```

Run the MCP server over stdio (it speaks JSON-RPC on stdin/stdout; use an MCP client such as the Phase 3 app's, or `uv run python scripts/demo_mcp.py` for a scripted client session):

```bash
uv run python -m staysmart.mcp_server
```

Run the HTTP application service (starts uvicorn on `127.0.0.1:8000`, launches the MCP server as a stdio subprocess, and serves the API under `/api`):

```bash
uv run python -m staysmart.app
```

Run the chat frontend in a second terminal (Vite dev server on `http://localhost:5173`, proxying `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173` and ask in plain language. `npm run build` produces the production bundle in `frontend/dist`.

Try it while the service runs:

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s -X POST http://127.0.0.1:8000/api/search -H "content-type: application/json" -d '{"destination":"Kyoto","check_in":"2026-12-04","check_out":"2026-12-07","max_nightly_budget":250.0,"min_rating":8.0,"amenities":["WIFI","BREAKFAST"]}'
curl -s -X POST http://127.0.0.1:8000/api/chat -H "content-type: application/json" -d '{"message":"Find a hotel in Kyoto for two guests in December under 250 with breakfast"}'
```

The chat endpoint needs a reachable LLM endpoint (`LLM_BASE_URL`, default `http://127.0.0.1:3425/v1`). If the model is down, chat returns 503 `llm_unavailable` while every structured endpoint keeps working.

This machine has several Python 3.13 interpreters and a `pip` that targets a different one than `python`. Always use `uv sync` and `uv run` so commands resolve against the project virtual environment. Never use bare `python` or `pip` for this repository.

Copy `.env.example` to `.env` to override configuration. No secrets are needed at this stage. `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` will be introduced with the agent in Phase 5 and are not read by current code.

No formatter or linter is configured. Adding one requires separate approval.

## Test and demo

Run the Python test suite (phases 1-5 and 7; phase 6 is the browser-driven frontend E2E documented in `tests/phase6/`):

```bash
uv run pytest tests/phase1 tests/phase2 tests/phase3 tests/phase4 tests/phase5 tests/phase7 -q
uv run python scripts/demo_provider.py
uv run python scripts/demo_mcp.py
uv run python scripts/demo_api.py
uv run python scripts/demo_rag.py
uv run python -m staysmart.rag ingest
uv run python scripts/demo_agent.py
```

The provider demo runs a realistic scenario: a Kyoto search with budget, rating and amenity filters; a Lisbon search with a different budget; a details lookup for a hotel with two room types; and an availability check for a fully sold-out stay. It writes a deterministic snapshot to `artifacts/provider_demo.json` (gitignored). `tests/phase1/test_e2e_snapshot.py` regenerates that artifact and compares it with `tests/phase1/golden/provider_demo.json`, which is authored from `tests/phase1/CONTRACT.md` rather than generated by the implementation. Line endings are normalized before comparison because Git may check out CRLF on Windows.

The MCP demo connects an in-process MCP client to the built server and runs the Phase 2 contract scenarios, including a comparison with an unresolved hotel id, two policy lookups and three pinned error cases. It writes `artifacts/mcp_demo.json`, checked against `tests/phase2/golden/mcp_demo.json` by `tests/phase2/test_mcp_e2e_snapshot.py`. Both demos print logging output to stderr and use `Settings()` defaults, so artifacts are pinned to the bundled dataset and unaffected by a local `.env`.

The API demo launches a real uvicorn server on an ephemeral port with the production stdio connector, calls every endpoint (search, details, availability, comparison with an unresolved id, two policy lookups, the chat stub) plus six error scenarios, and writes `artifacts/api_demo.json`, checked against `tests/phase3/golden/api_demo.json` by `tests/phase3/test_api_e2e_snapshot.py`.

The RAG demo ingests the knowledge corpus with FastEmbed into `data/rag/index` and runs six retrieval scenarios (pet policy, cancellation, check-in times, parking, room description, spa/pool by destination), writing `artifacts/rag_demo.json`, checked against `tests/phase4/golden/rag_demo.json` by `tests/phase4/test_rag_e2e_snapshot.py`. The first run downloads the free embedding model once; afterwards everything runs offline.

The agent demo runs three real-model chat scenarios end to end (filtered search, a policy question combining knowledge and structured data, and a comparison with recommendation) and writes `artifacts/agent_demo.json`. Model text is not deterministic, so `tests/phase5/test_agent_e2e.py` verifies it semantically and skips when `LLM_BASE_URL` is unreachable. All demos use `Settings()`-style defaults, so artifacts are pinned to the bundled data and unaffected by a local `.env`.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOTEL_PROVIDER` | `mock` | Provider implementation selector. Only `mock` exists. |
| `STAYSMART_DATASET_PATH` | bundled `data/hotels/v1/hotels.json` | Override the mock dataset |
| `STAYSMART_LOG_LEVEL` | `INFO` | Python logging level for the `staysmart` logger |
| `STAYSMART_CURRENCY` | `USD` | Expected currency; must match the dataset currency |
| `STAYSMART_WINDOW_DAYS` | `365` | Caps the booking horizon from the dataset anchor date |
| `STAYSMART_HTTP_HOST` | `127.0.0.1` | Bind address for the HTTP application service |
| `STAYSMART_HTTP_PORT` | `8000` | Port for the HTTP application service |
| `STAYSMART_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS |
| `STAYSMART_RAG_CORPUS_PATH` | bundled `data/knowledge/v1` | Knowledge corpus directory |
| `STAYSMART_RAG_INDEX_PATH` | `data/rag/index` | Generated vector index directory (gitignored) |
| `STAYSMART_RAG_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed model used for embeddings |
| `LLM_BASE_URL` | `http://127.0.0.1:3425/v1` | OpenAI-compatible endpoint for the chat agent |
| `LLM_API_KEY` | empty | API key; the default local endpoint needs none |
| `LLM_MODEL` | `auto/glm-5.3-flash` | Model id as the endpoint lists it |

Valid booking dates are `[anchor_date, anchor_date + min(dataset.window_days, settings.window_days))`. A stay must be 1 to 30 nights.

## Provider contract

`src/staysmart/providers/base.py` defines the `HotelProvider` Protocol. `MockHotelProvider` is the only implementation. Every returned object carries `data_source="mock"` and `is_live=False`. A partially or fully sold-out stay reports `available=False` and `total_price=None`; it never invents a total. `compare_hotels` and `get_hotel_policies` are service-layer derivations over the Protocol in `src/staysmart/services/`, and the MCP tools in `src/staysmart/mcp_server/` depend only on the Protocol and those services, never on the concrete provider.

The provider behavioral contract, inventory formula, expected values and failure-mode list live in [tests/phase1/CONTRACT.md](tests/phase1/CONTRACT.md). The service and MCP tool contract lives in [tests/phase2/CONTRACT.md](tests/phase2/CONTRACT.md). The HTTP API contract lives in [tests/phase3/CONTRACT.md](tests/phase3/CONTRACT.md). The RAG contract lives in [tests/phase4/CONTRACT.md](tests/phase4/CONTRACT.md). The agent contract lives in [tests/phase5/CONTRACT.md](tests/phase5/CONTRACT.md).

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
src/staysmart/app/mcp_client.py             MCP client connector seam (stdio and in-process)
src/staysmart/app/errors.py                 ApiError envelope and tool-failure classifier
src/staysmart/app/routes.py                 request models and seven API endpoints
src/staysmart/app/main.py                   create_app factory, lifespan and CORS
src/staysmart/app/__main__.py               python -m staysmart.app uvicorn entrypoint
src/staysmart/rag/corpus.py                 knowledge corpus loading and validation
src/staysmart/rag/chunking.py               heading-based chunking with size limits
src/staysmart/rag/embedder.py               FastEmbed and deterministic test embedders
src/staysmart/rag/index.py                  local vector index with cosine search
src/staysmart/rag/ingest.py                 build_index pipeline and ingest entrypoint
src/staysmart/rag/service.py                RagRetriever retrieval and context building
src/staysmart/agent/llm.py                  OpenAI-compatible client and scripted test model
src/staysmart/agent/tools.py                agent tool specs and dispatcher
src/staysmart/agent/prompts.py              grounded system prompt
src/staysmart/agent/agent.py                HotelAgent loop, budgets and safeguards
frontend/                                   Vite + React + TS chat UI (cards, dialogs, comparison)
data/hotels/v1/hotels.json                  versioned mock dataset
data/knowledge/v1/                          authored markdown knowledge corpus
scripts/demo_provider.py                    provider E2E artifact generator
scripts/demo_mcp.py                         MCP E2E artifact generator
scripts/demo_api.py                         HTTP API E2E artifact generator
scripts/demo_rag.py                         RAG E2E artifact generator
scripts/demo_agent.py                       agent E2E artifact generator (real LLM)
tests/phase1/                               provider contract, tests, golden artifact
tests/phase2/                               service and MCP contract, tests, golden artifact
tests/phase3/                               HTTP API contract, tests, golden artifact
tests/phase4/                               RAG contract, tests, golden artifact
tests/phase5/                               agent contract, tests, semantic E2E
tests/phase6/                               frontend contract and browser E2E interaction log
tests/phase7/                               integration journey, docs-consistency and artifact sweep
docs/                                       architecture and decision records
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - components, responsibilities and data flow
- [docs/DECISIONS.md](docs/DECISIONS.md) - architectural decisions and rationale
- [docs/MCP.md](docs/MCP.md) - MCP server, tools and schemas
- [docs/API.md](docs/API.md) - HTTP endpoints
- [docs/RAG.md](docs/RAG.md) - ingestion, retrieval and grounding
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) - agent execution and tool calling
