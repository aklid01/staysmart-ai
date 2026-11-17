from typing import Any

from demo_summaries import write_artifact

from staysmart.config import PROJECT_ROOT, Settings, configure_logging
from staysmart.rag.bootstrap import build_project_index
from staysmart.rag.corpus import load_corpus
from staysmart.rag.service import RagRetriever

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "rag_demo.json"

SCENARIOS = [
    (
        "pet_policy_kyoto",
        "Are dogs and cats allowed to stay at the townhouse?",
        {"hotel_id": "hotel-kyo-01"},
    ),
    (
        "cancellation_lisbon",
        "What happens if I cancel my booking at the boutique hotel in Alfama?",
        {"hotel_id": "hotel-lis-01"},
    ),
    (
        "check_in_kyoto",
        "What time can we check in and drop our bags in Kyoto?",
        {},
    ),
    (
        "parking_lisbon",
        "Is there parking for guests arriving by car in Baixa?",
        {},
    ),
    (
        "quiet_breakfast_room",
        "a quiet tatami room with futon bedding and breakfast included",
        {"hotel_id": "hotel-kyo-01"},
    ),
    (
        "spa_vancouver",
        "a waterfront hotel with a spa and an indoor pool",
        {"destination_id": "vancouver-ca"},
    ),
]


def result_record(retrieved: Any) -> dict[str, Any]:
    chunk = retrieved.chunk
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "heading": chunk.heading,
        "category": chunk.category,
        "hotel_id": chunk.hotel_id,
        "destination_id": chunk.destination_id,
        "source_path": chunk.source_path,
        "score": retrieved.score,
        "text": chunk.text,
    }


def source_record(source: Any) -> dict[str, Any]:
    return {
        "doc_id": source.doc_id,
        "title": source.title,
        "category": source.category,
        "chunk_count": source.chunk_count,
        "hotel_id": source.hotel_id,
        "destination_id": source.destination_id,
    }


def main() -> None:
    settings = Settings(log_level="WARNING")
    configure_logging(settings.log_level)
    index, embedder = build_project_index(settings)
    retriever = RagRetriever.load(settings.rag_index_path, embedder)

    queries: dict = {}
    for key, query, filters in SCENARIOS:
        bundle = retriever.build_context(query, top_k=4, **filters)
        queries[key] = {
            "query": query,
            "filters": filters,
            "results": [result_record(retrieved) for retrieved in bundle.chunks],
            "sources": [source_record(source) for source in bundle.sources],
        }

    payload = {
        "artifact_version": 1,
        "model": settings.rag_model,
        "embedding_dim": index.dim,
        "doc_count": len(load_corpus(settings.rag_corpus_path)),
        "chunk_count": index.chunk_count,
        "queries": queries,
    }

    write_artifact(ARTIFACT_PATH, payload)
    for key, record in queries.items():
        top = record["results"][0]
        print(f"{key}: top1={top['doc_id']} score={top['score']}")


if __name__ == "__main__":
    main()
