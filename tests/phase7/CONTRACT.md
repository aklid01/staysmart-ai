# Phase 7 integration testing, reliability and documentation contract

This document is the specification for Phase 7, the final phase. It is written before the Phase 7 tests and changes. Tests are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 7 adds no new features. It closes the Definition of Done with a cross-layer integration suite, small reliability fixes surfaced by earlier phases, and a documentation completion pass. The brief's twelve completion criteria are each verified by an automated test or an already-committed artifact, mapped below.

## Reliability changes

1. **Check-in/check-out answer variance (observed in Phase 5)**: the model sometimes answered "confirm with the property" even when the retrieved destination guide contained the exact times. The system prompt in `src/staysmart/agent/prompts.py` gains an explicit rule: check-in and check-out times are available in the destination-guide documents; when a retrieved chunk states them, quote the exact times and cite the document; only report them as unknown when no retrieved chunk states them. The behavior is re-verified by re-running the real-model agent demo; it stays semantically verified (model output is nondeterministic).
2. **Frontend lint**: `npm run lint` (oxlint, shipped by the scaffold) must pass clean on the Phase 6 sources.
3. **MCP session recovery**: if the stdio subprocess dies mid-session, calls fail with 503 `mcp_unavailable` and the process must be restarted; no auto-reconnect is added (documented limitation, decision record). No interleaving was observed on the shared session during testing, so no serialization lock is added; the decision records the evaluation.

## Integration suite (`tests/phase7/`)

- `test_integration_stack.py`: one full journey over every layer in-process - settings, provider, MCP server, Starlette app (in-process connector, scripted LLM, stub-embedder index), TestClient. The journey covers `/api/health`, a chat turn that calls `search_hotels` and `search_knowledge`, the structured search/details/policies/compare endpoints, and asserts cross-layer consistency: the hotel ids in the chat response's cards exist in the provider dataset, card data carries `data_source="mock"`, structured payloads match the phase-pinned values, and knowledge citations reference corpus docs.
- `test_docs_consistency.py`: documentation drift guards. Every HTTP route registered by `register_routes` appears in `docs/API.md`; every env-var-backed setting appears in the README configuration table and in `.env.example`; the README quickstart commands reference modules that exist (`python -m staysmart.app`, `python -m staysmart.rag`, `python -m staysmart.mcp_server`, the five demo scripts).
- `test_artifact_sweep.py`: regenerates the phase 1-4 demo artifacts through their script subprocesses (`demo_provider.py`, `demo_mcp.py`, `demo_api.py`, `demo_rag.py`), asserts each parses as JSON, carries `data_source="mock"` / `is_live=false` at the top level where applicable, and matches the committed goldens semantics (the byte-compares remain in their own phases). `demo_agent.py` runs only when the configured LLM endpoint is reachable (same skip rule as Phase 5); when it runs, its artifact is re-verified semantically. The sweep proves the whole demo surface works from a clean checkout state.

## Documentation completion

- README, `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` status tables mark every phase 0-7 implemented; remaining caveats removed or scoped to Phase 7 reality.
- Decision records updated: decision 11 (deferred dependencies) is now implemented; a new decision records the Phase 7 reliability choices (prompt rule, no auto-reconnect, no session lock) and the docs-consistency tests.
- The README "What is implemented" section and configuration table are the single source for operators; `docs/API.md` stays the endpoint contract.

## Definition of Done mapping

| Criterion | Verification |
| --- | --- |
| 1. Application starts locally | Quickstart commands exercised by tests and live runs throughout phases 3-6 |
| 2. Frontend talks to the Python service | Phase 6 browser E2E over the real proxy |
| 3. Agent interprets natural language | Phase 5 scripted + real-model E2E |
| 4. Agent invokes MCP tools | Phase 5 loop tests + artifact tool traces |
| 5. Search/details/availability vs mock provider | Phase 1-3 contract tests and goldens |
| 6. RAG retrieval with source references | Phase 4 golden snapshot + citations in agent responses |
| 7. Structured data + retrieved knowledge combined | Phase 5 knowledge tests + policy scenario |
| 8. Recommendations/comparisons in the UI | Phase 6 E2E comparison and card screenshots |
| 9. Errors and missing information handled | 422/4xx/5xx mapping tests, information-gaps UI, degraded health |
| 10. Automated tests pass | Full pytest suite green in Phase 7 |
| 11. Documentation explains the system | `test_docs_consistency.py` + final docs sweep |
| 12. No paid credentials required | Offline test paths in every phase; LLM endpoint optional |

## Failure modes to test

1. Full journey: chat with tool calls, structured endpoints and cross-layer id consistency in one test.
2. Docs drift: route missing from `docs/API.md`, env var missing from README or `.env.example` fails the suite.
3. Artifact sweep: every demo script runs from the current code and produces valid mock-marked JSON.
4. Agent demo skip: unreachable LLM endpoint skips cleanly without failing the suite.
