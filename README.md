# StaySmart AI

An educational MVP demonstrating MCP integration, LLM tool calling, RAG and API development through a hotel discovery and recommendation assistant.

> **Local mock hotel data only.** This project has no connection to Google Hotels or any live hotel inventory. It does not scrape Google Hotels, does not use reverse-engineered endpoints, and does not claim a live Google Hotels integration. It does not implement reservations, payments or booking transactions.

## What is implemented

| Phase | Status |
| --- | --- |
| 0 - Repository foundation, architecture, documentation scaffold | Implemented |
| 1 - Hotel data provider and structured operations | Not yet implemented |
| 2 - MCP server and tools | Not yet implemented |
| 3 - Starlette application service | Not yet implemented |
| 4 - RAG ingestion and retrieval | Not yet implemented |
| 5 - LLM agent orchestration | Not yet implemented |
| 6 - TypeScript frontend | Not yet implemented |
| 7 - Integration testing and final documentation | Not yet implemented |

Documentation describes implemented behavior only. Sections describing future phases are design notes, not available features.

## Stack

- Python 3.13, uv, pydantic v2
- Official Python MCP SDK 2.x over local stdio transport
- Starlette for the HTTP application layer (no FastAPI)
- FastEmbed and a lightweight local vector index for RAG
- Configurable OpenAI-compatible LLM endpoint
- TypeScript frontend
- pytest

No paid API credentials are required for the mock provider, the MCP tools, RAG retrieval or the test suite. A live LLM is optional and configured through environment variables in a later phase.

## Quickstart

```bash
uv python pin 3.13
uv sync
uv run python -c "import staysmart; print('staysmart ok')"
```

This machine has several Python 3.13 interpreters and a `pip` that targets a different one than `python`. Always use `uv sync` and `uv run` so commands resolve against the project virtual environment. Never use bare `python` or `pip` for this repository.

Copy `.env.example` to `.env` to override configuration. No secrets are needed at this stage. `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` will be introduced with the agent in Phase 5 and are not read by current code.

No formatter or linter is configured. Adding one requires separate approval.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HOTEL_PROVIDER` | `mock` | Provider implementation selector |
| `STAYSMART_DATASET_PATH` | bundled `data/hotels/v1/hotels.json` | Override the mock dataset |
| `STAYSMART_LOG_LEVEL` | `INFO` | Python logging level |
| `STAYSMART_CURRENCY` | `USD` | Currency used for mock prices |
| `STAYSMART_WINDOW_DAYS` | `365` | Booking horizon in days from the dataset anchor date |

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - components, responsibilities and data flow
- [docs/DECISIONS.md](docs/DECISIONS.md) - architectural decisions and rationale
- [docs/MCP.md](docs/MCP.md) - MCP server, tools and schemas
- [docs/API.md](docs/API.md) - HTTP endpoints
- [docs/RAG.md](docs/RAG.md) - ingestion, retrieval and grounding
- [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) - agent execution and tool calling
