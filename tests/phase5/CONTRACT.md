# Phase 5 LLM agent orchestration contract

This document is the specification for Phase 5. It is written before the agent implementation. Tests and the E2E artifact are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 5 delivers the LLM agent in `src/staysmart/agent/` and wires `POST /api/chat` to it, replacing the Phase 3 501 stub. The agent interprets natural-language requests, extracts structured parameters, calls MCP tools over the existing stdio session, retrieves knowledge through the Phase 4 `RagRetriever`, and produces a grounded final response that combines structured hotel data with retrieved context. No new MCP tools and no new HTTP endpoints beyond the chat upgrade exist in this phase. The frontend contract (Phase 6) consumes the chat response body documented here.

Everything is configurable through an OpenAI-compatible endpoint. No specific commercial provider is required, and every logic test runs offline against a scripted model. The real-model path is exercised by `scripts/demo_agent.py` and its E2E test, which skips when the configured endpoint is unreachable.

## Configuration additions

| Setting | Env var | Default |
| --- | --- | --- |
| `llm_base_url` | `LLM_BASE_URL` | `http://127.0.0.1:3425/v1` |
| `llm_api_key` | `LLM_API_KEY` | empty (no key needed for the local endpoint) |
| `llm_model` | `LLM_MODEL` | `auto/glm-5.3-flash` |

`llm_base_url` must include the `/v1` suffix as the OpenAI SDK expects. Empty `llm_api_key` is sent as the literal placeholder the SDK requires; the local endpoint ignores it. `LLM_*` variables are now read by code (README previously reserved them for this phase).

## Modules (`src/staysmart/agent/`)

- `llm.py` - `ChatLLM` protocol with `async complete(messages, tools) -> LLMCompletion`, where `LLMCompletion` carries `content: str | None` and `tool_calls: list[LLMToolCall]` (`id`, `name`, `arguments: dict`). `OpenAICompatLLM` implements it with the async OpenAI SDK client built from settings (base_url, api key placeholder, model, temperature 0.1, 120-second timeout) and raises `LLMUnavailableError` on connection, timeout and API errors. `ScriptedLLM` replays a fixed queue of `LLMCompletion` or exception objects and records every request for assertions.
- `tools.py` - the six agent-facing tools exposed to the model as OpenAI function specs: the five MCP tools plus `search_knowledge`. Schemas mirror the MCP tool inputs (ISO date strings, amenity enum values, no currency argument); `search_knowledge` takes `query` plus optional `hotel_id`, `destination_id` and `category` (the six corpus categories). Execution dispatches: hotel tools go through the MCP session (`session.call_tool`), `search_knowledge` calls `RagRetriever.build_context` and returns `{"formatted_context", "sources"}`.
- `prompts.py` - the system prompt: grounded assistant behavior (present only hotels, prices and availability returned by tools; never invent; all results are mock data marked `data_source="mock"`; report missing information instead of guessing), tool guidance (search for prices/availability, knowledge for policies and descriptions, combine both, cite sources as `[doc title]`), date guidance (no current date is given; resolve month-only requests to the nearest future dates inside the booking window), and recommendation guidance (explain why a hotel matches and name unmet preferences from `unmet_preferences`).
- `agent.py` - `HotelAgent(llm, retriever)` with `async run(message, *, history, session, conversation_id=None) -> AgentTurnResult`.
- `errors.py` - `LLMUnavailableError` and `AgentError`, both `StaySmartError` subclasses.

## Agent loop and safeguards

1. The message list is `system` + client-supplied `history` (`user`/`assistant` pairs, passed through, never stored server-side) + the new `user` message.
2. Loop bound: at most 6 model turns per chat request. Tool budget: at most 12 executed tool calls per chat request. When the turn limit is hit while the model still wants tools, the loop stops, appends one user instruction to summarize without tools, and makes one final model call with no tools available. When the tool budget is hit the same forced summary runs. The result then carries `stopped_early: true`.
3. Duplicate safeguard: an attempted call whose `(tool name, canonical arguments)` pair was already executed in this turn is not executed again; the model receives `Error: you already called <name> with these arguments. Use the earlier result.` and the trace marks the entry `duplicate`.
4. Tool failures: `ToolFailureError` text (classified provider message) and MCP transport failures become tool-result content beginning with `Error:`, so the model can correct arguments or degrade gracefully. The trace marks such entries `error`.
5. Model failures: a model turn that produces neither content nor tool calls yields one retry with a reminder; if it still yields nothing, the run raises `AgentError`.
6. The `hotels` array in the result is built exclusively from real tool payloads (`search_hotels` hits and `get_hotel_details` results, deduped by `hotel_id` with the details form winning). The model cannot inject hotel cards, so fabricated hotels cannot reach the frontend through this field. `comparison` is the `compare_hotels` payload when that tool ran, otherwise absent.

`AgentTurnResult` fields: `message` (final grounded text), `hotels` (list of tool-derived payloads), `comparison` (payload or `None`), `sources` (deduped `ContextSource` entries from `search_knowledge` calls, first-seen order, chunk counts merged), `tool_trace` (list of `{"tool", "status"}` with statuses `ok`, `error`, `duplicate`), `conversation_id` (echoed, or generated as a UUID when absent), `stopped_early` (bool).

## POST /api/chat (Phase 5 behavior)

Request (unchanged schema): `message` (required, min length 1), `conversation_id` (optional), `history` (optional list of `{role: user|assistant, content}`).

Response 200:

```json
{
  "message": "grounded text",
  "hotels": [],
  "comparison": null,
  "sources": [],
  "tool_trace": [{"tool": "search_hotels", "status": "ok"}],
  "conversation_id": "conv-1",
  "stopped_early": false
}
```

Error mapping additions: a raised `LLMUnavailableError` maps to 503 `llm_unavailable`; `RagError` (index missing) maps to 503 `rag_unavailable` with the actionable message to run ingestion. The retriever is loaded lazily on first chat use and cached on the app. Request validation failures stay 422 as before.

## Testing approach

Offline tests use `ScriptedLLM` plus the in-process MCP connector and the stub-embedder index, so no network and no model are needed: tool-call flows, error feedback and recovery, duplicate rejection, iteration/tool-budget bounds with forced summary, knowledge retrieval with source collection, hotel payload extraction and dedupe, and the chat endpoint (success, 422, 503 `llm_unavailable`, 503 `rag_unavailable`). The Phase 3 chat tests are updated to the new behavior (their 501 stub assertions are superseded by this contract) and `scripts/demo_api.py` records its chat scenario through a scripted model to keep the API artifact deterministic.

## E2E artifact

`scripts/demo_agent.py` builds the real stack (mock provider, MCP server in-process, FastEmbed index, `OpenAICompatLLM` against the configured endpoint), ingests the knowledge corpus if needed, runs three scenarios (filtered search, policy question combining knowledge and structured data, comparison plus recommendation) and writes `artifacts/agent_demo.json` with the message, tool trace, hotel ids, sources and comparison per scenario. Because model text is not deterministic, this artifact is verified by semantic assertions instead of a byte-for-byte golden: `tests/phase5/test_agent_e2e.py` skips when the configured endpoint is unreachable and otherwise asserts the tools used, the hotel ids involved (mock dataset ids only), source presence for the policy scenario, and that every recorded hotel id carries mock markers. This is a deliberate deviation from the earlier byte-compared goldens, caused by LLM nondeterminism; the deterministic provider data remains byte-pinned in the phase 1-4 artifacts.

## Failure modes to test

1. Single tool call then grounded final answer; tool payload JSON reaches the model; trace is `ok`.
2. Unknown destination error fed back, then corrected call succeeds.
3. Exact duplicate call rejected without execution and marked in the trace.
4. Permanently tool-calling model stopped by the turn limit; forced summary produced; `stopped_early` true; call count bounded.
5. `search_knowledge` executes through the retriever and sources land in the result.
6. Search hit plus details for the same hotel dedupe to one entry with the details form.
7. Chat endpoint returns 200 with the full body and echoes `conversation_id`; generates one when absent.
8. Chat endpoint maps an unreachable model to 503 `llm_unavailable`.
9. Chat endpoint maps a missing index to 503 `rag_unavailable` with the ingest instruction.
10. Empty message and invalid history roles stay 422.
