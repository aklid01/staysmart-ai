# RAG ingestion, retrieval and grounding

Status: implemented (Phase 4, retrieval). Everything below describes behavior that exists in `src/staysmart/rag/` and `data/knowledge/v1/` and is covered by `tests/phase4/`. Grounded response generation over this retrieval arrives with the LLM agent in Phase 5.

## What retrieval is for

The knowledge base supplies descriptive and policy context that the structured provider does not carry: house explanations, room descriptions, amenity details, cancellation and pet policy wording, and destination check-in/check-out requirements. Retrieval is a separate channel from structured hotel search:

- Prices and availability never come from RAG documents. The corpus contains none, and a consistency test enforces it.
- The structured provider honestly reports check-in and check-out times as `information_gaps`; the destination documents are the legitimate source for those facts.
- Hotel facts (pet rules, cancellation tiers, amenities) agree with the mock dataset by construction, and tests pin the corpus to the dataset so the two cannot silently diverge.

## Knowledge corpus

`data/knowledge/v1/` holds 53 authored markdown documents: five per hotel (general, rooms, amenities, cancellation, pet policy) and one check-in/check-out guide per destination. Each file starts with a `---` frontmatter block:

```markdown
---
doc_id: hotel-lis-01-cancellation
category: cancellation
title: Alfama Riverside Boutique cancellation and refund policy
hotel_id: hotel-lis-01
---

## Cancellation terms

Free cancellation applies until 2 days before check-in. ...
```

Categories are `general`, `rooms`, `amenities`, `cancellation`, `pet_policy` and `check_in_check_out`. Documents carry no prices (`$`, `per night`), no availability claims (`sold out`, `rooms left`), and pet/cancellation wording is pinned to the dataset values by tests in `tests/phase4/test_consistency.py`.

## Ingestion pipeline

```bash
uv run python -m staysmart.rag ingest
```

1. **Load and validate** (`corpus.py`): frontmatter schema, category-to-filename match, unique `doc_id`s, hotel/destination id placement.
2. **Chunk** (`chunking.py`): the body splits on `## ` headings; text before the first heading becomes an overview chunk. Sections longer than 600 characters split on paragraph boundaries (no overlap). Each chunk keeps `doc_id`, `title`, `category`, `heading`, source path and its position.
3. **Enrich**: hotel chunks gain the `destination_id` resolved from the mock dataset, so destination filters can return hotel documents.
4. **Embed** (`embedder.py`): `FastEmbedEmbedder` runs `BAAI/bge-small-en-v1.5` (384 dimensions) over `<title> - <heading>\n<text>` and unit-normalizes every vector. The first run downloads the free model into the local fastembed cache; afterwards it is offline.
5. **Persist** (`index.py`): `vectors.npy` plus `chunks.json` under `STAYSMART_RAG_INDEX_PATH` (default `data/rag/index`, gitignored). Loading validates counts and dimensions and raises `RagError` with an actionable message otherwise.

## Retrieval

`RagRetriever` wraps a loaded index plus an embedder:

- `retrieve(query, hotel_id=None, destination_id=None, category=None, top_k=4)` embeds the query, filters chunks by metadata, ranks by cosine similarity (dot product of unit vectors) and returns chunks with 4-decimal scores. An empty result after filtering is an empty list; a blank query raises `RagError`.
- `build_context(...)` additionally assembles a `ContextBundle`: numbered `[n] Title - Heading: text` blocks truncated to a character budget at chunk boundaries, plus `sources` - one entry per cited document in first-seen order with its category, id and chunk count. This bundle is what the Phase 5 agent pastes into its prompt and cites.

```python
retriever = RagRetriever.load(settings.rag_index_path, FastEmbedEmbedder(settings.rag_model))
bundle = retriever.build_context("Are dogs and cats allowed to stay at the townhouse?", hotel_id="hotel-kyo-01")
```

The embedder is an injectable protocol. Tests use a deterministic hash-based stub embedder, so all corpus, chunking, filtering and ranking logic is testable offline; only the demo snapshot needs the real model.

## Source attribution

Every chunk carries provenance, and every context bundle summarizes it: `doc_id`, document `title`, `category`, the `hotel_id`/`destination_id` it belongs to, and the corpus-relative source path. Grounded answers in Phase 5 will cite these sources as text; the UI renders citations as text chips. Images never flow through the retrieval channel.

## Testing and E2E artifact

```bash
uv run pytest tests/phase4 -q
uv run python scripts/demo_rag.py
```

`tests/phase4/CONTRACT.md` is the behavioral specification, written before the implementation. Offline tests cover corpus validation, the corpus-vs-dataset consistency rules, chunking, index persistence, and retrieval with the stub embedder (41 tests). `scripts/demo_rag.py` ingests with FastEmbed and runs six pinned scenarios (pet policy, cancellation, check-in, parking, room description, spa/pool by destination); `tests/phase4/test_rag_e2e_snapshot.py` byte-compares `artifacts/rag_demo.json` against the golden `tests/phase4/golden/rag_demo.json` after CRLF normalization and asserts the semantic rankings independently. Scores are rounded to 4 decimals so the artifact is stable.
