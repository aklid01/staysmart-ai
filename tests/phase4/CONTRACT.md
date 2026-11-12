# Phase 4 RAG ingestion and retrieval contract

This document is the specification for Phase 4. It is written before the RAG implementation and the knowledge corpus. Tests and the golden E2E artifact are derived from it. If implementation and contract disagree, the contract wins and the implementation is fixed.

## Scope

Phase 4 delivers the knowledge corpus in `data/knowledge/v1/` and the retrieval stack in `src/staysmart/rag/`: document loading with frontmatter metadata, markdown chunking, FastEmbed embeddings, a lightweight local vector index with metadata filters, semantic retrieval, context construction and source attribution. No LLM, no HTTP endpoints and no MCP tools exist in this phase; the Phase 5 agent consumes the retrieval service, and the Phase 6 frontend only ever sees citations as text.

Retrieval stays separate from structured hotel search. The corpus contains no prices, no availability claims and no live-data claims. Prices and availability come only from the provider through the MCP tools.

## Technology

- Embeddings: `fastembed` with `BAAI/bge-small-en-v1.5` (384 dimensions, free download, cached locally after first use). Verified installable on Python 3.13 before implementation.
- Vector storage: a local index directory with `vectors.npy` plus `chunks.json`, searched with numpy cosine similarity (vectors are unit-normalized, so cosine is a dot product). No external vector database.
- `numpy` is declared as a direct dependency because the index uses it. `fastembed` brings `onnxruntime`, `tokenizers` and their transitive dependencies.
- The embedder is an injectable protocol. Tests use a deterministic hash-based stub embedder so all corpus, chunking, filtering and ranking logic is testable offline; the real FastEmbed model is exercised by the demo script and its snapshot test.

## Configuration additions

| Setting | Env var | Default |
| --- | --- | --- |
| `rag_corpus_path` | `STAYSMART_RAG_CORPUS_PATH` | `data/knowledge/v1` |
| `rag_index_path` | `STAYSMART_RAG_INDEX_PATH` | `data/rag/index` |
| `rag_model` | `STAYSMART_RAG_MODEL` | `BAAI/bge-small-en-v1.5` |

Invalid values follow the existing settings behavior. The generated index directory is gitignored.

## Corpus shape

Layout, 53 documents total (10 hotels x 5 categories plus 3 destinations):

```
data/knowledge/v1/
  hotels/<hotel_id>/general.md
  hotels/<hotel_id>/rooms.md
  hotels/<hotel_id>/amenities.md
  hotels/<hotel_id>/cancellation.md
  hotels/<hotel_id>/pet-policy.md
  destinations/<destination_id>/check-in-check-out.md
```

Each file starts with a `---` delimited frontmatter of simple `key: value` lines, then a markdown body with `## Heading` sections:

| Key | Required | Meaning |
| --- | --- | --- |
| `doc_id` | yes | Unique id: `hotel-lis-01-general`, `lisbon-pt-check-in-check-out`, and so on |
| `category` | yes | One of `general`, `rooms`, `amenities`, `cancellation`, `pet_policy`, `check_in_check_out` |
| `title` | yes | Human-readable title used in citations |
| `hotel_id` | hotel docs | Must exist in the dataset |
| `destination_id` | destination docs | Must exist in the dataset |

Validation rules: frontmatter keys outside this set are rejected; `category` must match the file name mapping (`general.md` -> `general`, `pet-policy.md` -> `pet_policy`, `check-in-check-out.md` -> `check_in_check_out`, and so on); `doc_id` values are unique across the corpus; hotel docs carry `hotel_id` and not `destination_id`, destination docs the reverse. Every dataset hotel has exactly the five hotel docs and every dataset destination exactly one destination doc.

## Consistency rules (corpus vs dataset, enforced by tests)

The corpus is authored, but its facts are pinned to the dataset by tests so the two can never silently diverge:

1. **Cancellation**: every refundable hotel's `cancellation.md` contains the sentence `Free cancellation applies until <N> days before check-in` where N equals `free_cancellation_days`; partial policies additionally contain `<M>-night penalty` where M equals `penalty_nights`. Non-refundable hotels' docs contain `non-refundable` and no `until <digits> days before check-in` sentence. Refundable docs never contain `non-refundable`.
2. **Pet policy**: hotels with the `PET_FRIENDLY` amenity contain `Pets are allowed` and not `Pets are not allowed`; hotels without it contain `Pets are not allowed` and not `Pets are allowed`.
3. **Amenities**: every dataset amenity appears in the hotel's `amenities.md` in its pinned lowercase phrase (`wifi`, `breakfast`, `air conditioning`, `pool`, `gym`, `parking`, `spa`, `pet-friendly`, `restaurant`, `shuttle`); phrases for amenities the hotel does not have (except `wifi`, universal) must not appear in that file.
4. **Rooms**: every room type's name appears in `rooms.md`, each room section states `sleeps up to <max_occupancy> guests`, and the bed type word appears. No rates or prices anywhere.
5. **General**: `general.md` contains `<star_rating>-star` for the hotel's star rating.
6. **Check-in/check-out**: destination docs state pinned times - Lisbon `Check-in starts at 15:00` / `Check-out is by 11:00`; Kyoto `15:00` / `10:00`; Vancouver `16:00` / `11:00`. These are the legitimate document source for facts the structured provider honestly reports as `information_gaps`.
7. **No pricing or availability**: no document contains a `$` followed by digits, the phrase `per night` with a number, `total price`, `nightly rate`, `sold out`, or `rooms left`.

## Chunking

- The body is split on `## ` headings into sections. Text before the first heading becomes a chunk whose heading is the document title.
- Sections longer than 600 characters are split on paragraph boundaries and accumulated into chunks of at most 600 characters (single paragraphs longer than the limit stay one chunk). No overlap.
- Chunk metadata: `chunk_id` (`<doc_id>:<chunk_index>`, 0-based within the doc), `doc_id`, `title`, `category`, `hotel_id` or `destination_id`, `heading` (section heading, or title for the overview chunk), `source_path` (corpus-relative path), `text`. Hotel chunks additionally carry the `destination_id` resolved from the dataset at ingestion, so destination filters can return hotel documents; destination-guide chunks carry `destination_id` only.
- Embedded text per chunk is `<title> - <heading>\n<text>` so citations stay grounded in the chunk's topic.

## Embedding and index

- `Embedder` protocol: `embed_documents(texts: list[str]) -> list[list[float]]` and `embed_query(text: str) -> list[float]`.
- `FastEmbedEmbedder` wraps `fastembed.TextEmbedding` with the configured model, unit-normalizes every vector, and requires a fixed dimension of 384 for `bge-small-en-v1.5`.
- `DeterministicEmbedder` (tests only): 64-dimensional unit vectors derived from SHA-256 of the lowercased whitespace-split tokens, so the same text always yields the same vector and repeated tokens increase weight. Semantically meaningless, plumbing-only.
- `VectorIndex`: stores the normalized vector matrix and the chunk records; `search(query_vector, hotel_id=None, destination_id=None, category=None, top_k=4)` filters by metadata before ranking, scores by dot product, and returns `(chunk, score)` pairs sorted by descending score. Score values are rounded to 4 decimals in responses and artifacts.
- Persistence: `save` writes `vectors.npy` and `chunks.json` into the index directory; `load` restores both and raises `RagError` when counts or dimensions mismatch or files are missing.
- `RagError` joins the error taxonomy with code `rag_error` (defined in the rag package, raised for corpus, index and embedder failures).

## Retrieval service

`RagRetriever` is constructed from a loaded index plus an embedder:

- `retrieve(query, *, hotel_id=None, destination_id=None, category=None, top_k=4) -> list[RetrievedChunk]`: embeds the query, searches the index, returns chunks with 4-decimal scores. An empty result after filtering is an empty list, never an error. A blank query raises `RagError`.
- `build_context(query, *, hotel_id=None, destination_id=None, category=None, top_k=4, max_chars=1200) -> ContextBundle`: retrieves, then assembles `formatted_context` - chunks joined as numbered `[n] <title> - <heading>: <text>` blocks truncated to the char budget at chunk boundaries - plus `sources`: one entry per cited document in first-seen order with `doc_id`, `title`, `category`, and `hotel_id`/`destination_id`, plus the chunk count. The bundle is what the Phase 5 agent pastes into its prompt and cites.

## Ingestion entrypoint

```bash
uv run python -m staysmart.rag ingest
```

Loads the corpus, validates it, chunks it, resolves each hotel chunk's `destination_id` from the dataset, embeds with FastEmbed, and writes the index directory. Prints counts to stderr and logs via the `staysmart` logger. An invalid corpus or missing model fails with an actionable `RagError`.

## Testing approach

`tests/phase4/` mirrors the earlier phases. Offline tests (no network, stub embedder): frontmatter parsing and corpus validation failures, chunking rules (heading split, 600-char limit, metadata, chunk ids), index save/load round-trip, retrieval ranking/filters/top_k/empty results with the stub embedder, context bundle assembly and source ordering, and the corpus-vs-dataset consistency rules above. Real-model E2E: `scripts/demo_rag.py` ingests the corpus with FastEmbed, runs the pinned scenarios, and writes `artifacts/rag_demo.json` deterministically (scores rounded to 4 decimals); `test_rag_e2e_snapshot.py` byte-compares it with the spec-authored golden `tests/phase4/golden/rag_demo.json` after CRLF normalization and asserts the semantic values independently. The first run downloads the free model into the local fastembed cache; afterwards the suite runs offline. No paid credentials anywhere.

## Demo scenarios (pinned)

All scores rounded to 4 decimals; `top_k` 4 unless stated. Artifact keys: `artifact_version: 1`, `model`, `embedding_dim: 384`, `doc_count: 53`, `chunk_count`, `queries`, each with `query`, `filters`, `results` (chunk metadata, text, score) and `sources`.

| Key | Query | Filters | Expected top-1 |
| --- | --- | --- | --- |
| `pet_policy_kyoto` | `Are dogs and cats allowed to stay at the townhouse?` | `hotel_id: hotel-kyo-01` | `hotel-kyo-01-pet-policy` |
| `cancellation_lisbon` | `What happens if I cancel my booking at the boutique hotel in Alfama?` | `hotel_id: hotel-lis-01` | `hotel-lis-01-cancellation` |
| `check_in_kyoto` | `What time can we check in and drop our bags in Kyoto?` | none | `kyoto-jp-check-in-check-out` |
| `parking_lisbon` | `Is there parking for guests arriving by car in Baixa?` | none | `hotel-lis-02-amenities` |
| `quiet_breakfast_room` | `a quiet tatami room with futon bedding and breakfast included` | `hotel_id: hotel-kyo-01` | `hotel-kyo-01-rooms` |
| `spa_vancouver` | `a waterfront hotel with a spa and an indoor pool` | `destination_id: vancouver-ca` | `hotel-van-01-general` or `hotel-van-01-amenities` (whichever ranks first) |

The last scenario ranks semantically, so the contract pins that a `hotel-van-01` doc ranks first among the Vancouver-filtered candidates; the artifact records whatever the model produces and the golden pins it.
