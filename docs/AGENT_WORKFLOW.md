# Agent workflow and tool calling

Status: implemented (Phase 5). Everything below describes behavior that exists in `src/staysmart/agent/` and is covered by `tests/phase5/`.

## Overview

`HotelAgent` turns one natural-language message into a grounded answer by looping between the LLM and tools. It consumes two channels built in earlier phases:

- **Structured channel**: the five MCP hotel tools over the app's long-lived stdio session. Tool results are mock-provider payloads (`data_source="mock"`, `is_live=False`) and are the only source of hotels, prices and availability.
- **Knowledge channel**: the Phase 4 `RagRetriever` over the authored corpus. It supplies pet rules, check-in/check-out requirements, room and amenity descriptions and destination guidance, always with per-document sources. It never contains prices or availability.

```
user message
  -> [system prompt + history + message] --> LLM (OpenAI-compatible endpoint)
  <- tool calls (or final answer)
  -> execute tool calls: 5x via MCP session, 1x via RagRetriever
  -> append tool results as JSON, loop (max 6 turns, max 12 tool calls)
  <- final grounded message
  -> AgentTurnResult { message, hotels, comparison, sources, tool_trace, ... }
```

## Model configuration

`OpenAICompatLLM` wraps the async OpenAI SDK against any OpenAI-compatible endpoint:

| Env var | Default | Meaning |
| --- | --- | --- |
| `LLM_BASE_URL` | `http://127.0.0.1:3425/v1` | Base URL including `/v1` |
| `LLM_API_KEY` | empty | Sent as a placeholder when empty; the local endpoint ignores it |
| `LLM_MODEL` | `auto/glm-5.3-flash` | Model id as the endpoint lists it |

Temperature is 0.1 and the per-request timeout is 120 seconds. Connection, timeout and API errors raise `LLMUnavailableError`, which the HTTP layer maps to 503 `llm_unavailable`. `ScriptedLLM` replays fixed completions for offline tests.

## Tools exposed to the model

Six OpenAI function specs (`src/staysmart/agent/tools.py`): `search_hotels`, `get_hotel_details`, `check_availability`, `compare_hotels`, `get_hotel_policies` (schemas mirror the MCP tool inputs; no currency argument) plus `search_knowledge` (`query` plus optional `hotel_id`, `destination_id`, `category`). Execution dispatches hotel tools through `session.call_tool` and knowledge calls through `RagRetriever.build_context`, returning `{"formatted_context", "sources"}`.

## Loop and safeguards

1. **Bounded turns**: at most 6 model turns per chat request. If the model still wants tools after the limit, the agent appends one instruction to summarize without tools and makes a final call with no tools available; the result is flagged `stopped_early: true`.
2. **Bounded tool calls**: at most 12 executed tool calls per chat request, shared across turns. The same forced summary applies.
3. **Duplicate rejection**: an attempted call whose `(name, canonical arguments)` pair already ran is not executed; the model receives an error telling it to use the earlier result, and the trace records status `duplicate`.
4. **Error feedback**: tool failures (classified provider messages via `ToolFailureError`) and MCP transport failures become tool-result content starting with `Error:`, so the model can correct arguments or degrade gracefully. Status `error` in the trace.
5. **Grounded cards**: the `hotels` array is assembled exclusively from real `search_hotels` and `get_hotel_details` payloads (deduped by `hotel_id`, details winning). The model cannot inject hotel cards, so fabricated hotels cannot reach the frontend through this field.
6. **Empty responses**: a model turn with neither content nor tool calls triggers one retry; a second empty turn raises `AgentError`.
7. **System prompt grounding**: the prompt forbids inventing facts, requires mock-data disclosure, explains how to resolve vague dates into the booking window, and requires honest unmet-preference reporting.

## Conversation context

The client supplies `conversation_id` and `history` (`user`/`assistant` pairs) on each chat request; the server stores nothing between requests. The history is passed through to the model in order. A missing `conversation_id` is generated as a short UUID and echoed back.

## POST /api/chat

Request: `{"message", "conversation_id?", "history?"}`. Response 200:

```json
{
  "message": "grounded text with [document title] citations",
  "hotels": [ ... search hits and details payloads ... ],
  "comparison": null,
  "sources": [ {"doc_id", "title", "category", "chunk_count", "hotel_id", "destination_id"} ],
  "tool_trace": [ {"tool": "search_hotels", "status": "ok"} ],
  "conversation_id": "conv-1",
  "stopped_early": false
}
```

Unreachable model -> 503 `llm_unavailable`. Missing vector index -> 503 `rag_unavailable` with the instruction to run `python -m staysmart.rag ingest`. Request validation stays 422.

## Testing and E2E artifact

Offline tests (`tests/phase5/`) use `ScriptedLLM` plus the in-process MCP connector and the stub-embedder index: tool flows, error feedback, duplicate rejection, both budget bounds with forced summaries, knowledge sourcing, card dedupe and the endpoint contract including both 503 paths. `scripts/demo_agent.py` runs three real-model scenarios against the configured endpoint and writes `artifacts/agent_demo.json`; `tests/phase5/test_agent_e2e.py` skips when the endpoint is unreachable and otherwise asserts the tool usage, hotel ids (mock dataset ids only) and source presence semantically. Model text is not deterministic, so this artifact is verified semantically rather than byte-compared; the provider data behind it remains byte-pinned by the phase 1-4 goldens.

```bash
uv run pytest tests/phase5 -q
uv run python scripts/demo_agent.py
```
