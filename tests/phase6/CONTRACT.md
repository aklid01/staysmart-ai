# Phase 6 TypeScript frontend contract

This document is the specification for Phase 6. It is written before the frontend implementation. The browser E2E verification in `artifacts/ui_demo/` is derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 6 delivers `frontend/`, a Vite + React + TypeScript single-view application that talks to the Starlette service. The frontend holds no agent logic, no retrieval logic and no provider logic: chat answers, hotel cards, comparisons and citations all render from API responses. The stack choices: npm, Vite dev server with an `/api` proxy to the backend on port 8000, React function components with hooks only (no router, no state library, no UI component framework), one hand-written CSS file with design tokens. The brief allows "hotel images or appropriate placeholders": cards use destination-themed gradient placeholders with the hotel initial, no binary images and no runtime network image loads.

## Backend integration

- `POST /api/chat` carries `{message, conversation_id, history}`. The client generates the `conversation_id` once per browser session and sends the recent history (last 10 entries) each turn. The response renders as: `message` (assistant text with markdown-lite rendering limited to paragraphs, bold and inline code), `hotels` as card grids, `comparison` as a table, `sources` as citation chips, `tool_trace` shown as a small tool chip row when present, and `stopped_early` surfaced as a notice.
- `GET /api/hotels/{hotel_id}` (with the stay dates from the last chat query when available) opens a details dialog with room quotes, cancellation policy and mock markers.
- `GET /api/hotels/{hotel_id}/policies` opens a policy dialog with the cancellation facts, pet policy and `pet_policy_source`, explicit `information_gaps` chips, and check-in/check-out times when present.
- `GET /api/health` on mount drives the header status dot (ok/degraded) and the persistent "mock data" badge.
- Every request renders its failure through one error banner style: `error.code` plus `error.message` from the `{"error": {...}}` envelope; the chat thread keeps the user's message visible so it can be retried.
- Loading states: a typing indicator row while chat is in flight; dialog spinners while details or policies load. No request runs concurrently with itself; the send button disables while in flight.

## Interface contents (brief mapping)

| Brief requirement | Implementation |
| --- | --- |
| Chat interface | Single-column thread, user bubbles right, assistant blocks left |
| Natural-language search input | Autosizing textarea plus Send button at the bottom |
| Hotel result cards | Card grid per assistant message built from `hotels[]` |
| Images or placeholders | Destination gradient placeholder with hotel initial |
| Pricing and rating | Nightly average, total when fully available, star and guest ratings |
| Amenity indicators | Chip row from the hotel's amenity list |
| Hotel comparison view | Table from the `comparison` payload with unresolved ids and unmet preferences rows |
| Hotel details | Dialog from the details endpoint |
| Policy information and source references | Dialog from the policies endpoint plus citation chips under assistant messages |
| Loading and error states | Typing indicator, dialog spinners, error banner, degraded health dot |

## Layout and style rules

- One page, one CSS file, CSS custom properties for the palette (deep teal primary, warm amber accent, light neutral surfaces), system font stack.
- Responsive: single column below 720px; card grid collapses to one column; dialogs become full-width sheets.
- No animations beyond a gentle fade for new messages and a pulsing typing indicator; no dashboards, no charts.

## E2E verification

Black-box browser testing against the real stack (Vite dev server + uvicorn backend with the configured LLM endpoint). The session performs the contract scenarios, captures a screenshot per scenario into `artifacts/ui_demo/` and records `artifacts/ui_demo/interaction_log.json` with the steps and observed assertions:

1. Load: header, health dot, mock badge, empty chat prompt visible.
2. Search request via chat: user bubble, typing indicator, assistant reply with at least one hotel card showing name, nightly price, ratings, amenity chips, mock badge.
3. Details dialog: opens from a card, shows room quotes and closes.
4. Policy dialog: opens from a card, shows cancellation terms, pet policy, information gaps chips and closes.
5. Comparison request via chat: comparison table renders with hotel columns, unresolved-id note when applicable.
6. Error state: with the backend stopped, a chat attempt shows the error banner with the failure code (connection failure rendered as a readable message).

The E2E skips cleanly if the backend or LLM endpoint is not running; screenshots and the interaction log remain the reproducible artifact. Deterministic backend behavior behind the UI is already byte-pinned by the phase 1-5 artifacts, so the frontend artifact verifies integration and rendering, not model wording.
