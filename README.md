# StaySmart AI

Find hotels by chatting. Describe the trip in plain language and the assistant searches a mock hotel inventory, compares options, answers policy questions from a knowledge base and shows check-in times, prices and availability with source references.

> **Mock data only.** Hotels, prices and availability come from a bundled mock dataset. Nothing here connects to a real booking system, takes reservations or handles payments.

## What you get

- A chat interface: ask for "a hotel in Kyoto in December under 250 with breakfast" and get cards with prices, ratings, amenities and cancellation badges.
- Structured endpoints for search, details, availability, policies and comparison, so the same data is reachable without the chat.
- Grounded answers: hotel facts come from tool calls, policy and check-in facts come from a retrieved markdown knowledge base, and every claim carries its source.
- Honest empty states: sold-out stays never show a total price, unknown policies are labeled unknown, unverified preferences are listed as unmet.

## Stack

Python 3.13 and uv, pydantic v2, the official MCP Python SDK over stdio, Starlette, FastEmbed with a local numpy vector index, an OpenAI-compatible LLM endpoint, and a Vite + React + TypeScript frontend.

## Quickstart

```bash
uv sync
uv run python -m staysmart.app

> The API is unauthenticated by design and binds to 127.0.0.1 by default; the loopback address is the trust boundary. Do not expose it to public networks without adding auth.
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` and start chatting. The chat agent needs an OpenAI-compatible LLM endpoint (`LLM_BASE_URL`, default `http://127.0.0.1:3425/v1`, no key); when it is down, chat returns 503 while every structured endpoint keeps working.

Other entry points:

```bash
uv run python -m staysmart.mcp_server   # five MCP hotel tools over stdio
uv run python -m staysmart.rag ingest   # build the vector index (free one-time model download)
uv run pytest                           # 217 tests, fully offline paths included
```

## Configuration

Copy `.env.example` to `.env` to override any of these.

| Variable                    | Default                                       | Meaning                                               |
| --------------------------- | --------------------------------------------- | ----------------------------------------------------- |
| `HOTEL_PROVIDER`            | `mock`                                        | Provider implementation selector. Only `mock` exists. |
| `STAYSMART_DATASET_PATH`    | bundled `data/hotels/v1/hotels.json`          | Override the mock dataset                             |
| `STAYSMART_LOG_LEVEL`       | `INFO`                                        | Python logging level for the `staysmart` logger       |
| `STAYSMART_CURRENCY`        | `USD`                                         | Expected currency; must match the dataset currency    |
| `STAYSMART_WINDOW_DAYS`     | `365`                                         | Caps the booking horizon from the dataset anchor date |
| `STAYSMART_HTTP_HOST`       | `127.0.0.1`                                   | Bind address for the HTTP application service         |
| `STAYSMART_HTTP_PORT`       | `8000`                                        | Port for the HTTP application service                 |
| `STAYSMART_CORS_ORIGINS`    | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated browser origins allowed by CORS       |
| `STAYSMART_RAG_CORPUS_PATH` | bundled `data/knowledge/v1`                   | Knowledge corpus directory                            |
| `STAYSMART_RAG_INDEX_PATH`  | `data/rag/index`                              | Generated vector index directory (gitignored)         |
| `STAYSMART_RAG_MODEL`       | `BAAI/bge-small-en-v1.5`                      | FastEmbed model used for embeddings                   |
| `LLM_BASE_URL`              | `http://127.0.0.1:3425/v1`                    | OpenAI-compatible endpoint for the chat agent         |
| `LLM_API_KEY`               | empty                                         | API key; the default local endpoint needs none        |
| `LLM_MODEL`                 | `auto/glm-5.3-flash`                          | Model id as the endpoint lists it                     |

## Layout

```
src/staysmart/        domain models, mock provider, MCP server, Starlette app, RAG, agent
frontend/             Vite + React + TS chat UI
data/                 mock hotel dataset and markdown knowledge corpus
scripts/              demo scripts that regenerate reproducible JSON artifacts
tests/                pytest suite with golden snapshot artifacts
```

Tooling: `uv run ruff check .` and `uv run ruff format .` for Python; `npm run lint` and `npm run format` in `frontend/`.
