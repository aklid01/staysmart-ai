import asyncio
import json
import logging

from mcp import Client

from staysmart.agent.agent import HotelAgent
from staysmart.agent.llm import OpenAICompatLLM
from staysmart.app.mcp_client import SdkMcpSession
from staysmart.config import PROJECT_ROOT, Settings, configure_logging

logger = logging.getLogger("staysmart")
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import get_provider
from staysmart.rag.corpus import load_corpus
from staysmart.rag.embedder import FastEmbedEmbedder
from staysmart.rag.ingest import build_index
from staysmart.rag.service import RagRetriever

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "agent_demo.json"

SCENARIOS = [
    (
        "search_kyoto",
        "Find hotels in Kyoto for two guests from December 4 to 7, 2026, under 250 USD per night, with wifi and breakfast.",
    ),
    (
        "policy_kyoto",
        "Can I bring my dog to Gion Machiya Stay? And what time is check-in in Kyoto?",
    ),
    (
        "compare_lisbon",
        "Compare Alfama Riverside Boutique and Baixa Central Hotel for December 4-7, 2026 and recommend one for a budget traveller.",
    ),
]


def hotel_ids(result) -> list[str]:
    return [entry["hotel"]["hotel_id"] for entry in result.hotels]


def source_records(result) -> list[dict]:
    return [
        {
            "doc_id": source.doc_id,
            "title": source.title,
            "category": source.category,
            "chunk_count": source.chunk_count,
            "hotel_id": source.hotel_id,
            "destination_id": source.destination_id,
        }
        for source in result.sources
    ]


async def run() -> dict:
    settings = Settings(log_level="WARNING")
    configure_logging(settings.log_level)

    dataset = load_dataset(settings.dataset_path)
    destination_by_hotel = {hotel.hotel_id: hotel.destination_id for hotel in dataset.hotels}
    embedder = FastEmbedEmbedder(settings.rag_model)
    if not settings.rag_index_path.exists():
        build_index(
            settings.rag_corpus_path,
            settings.rag_index_path,
            embedder,
            destination_by_hotel,
        )
    retriever = RagRetriever.load(settings.rag_index_path, embedder)

    provider = get_provider(settings)
    server = build_mcp_server(settings, provider)
    llm = OpenAICompatLLM(settings)
    agent = HotelAgent(llm, retriever)

    scenarios: dict[str, dict] = {}
    async with Client(server=server) as connected:
        session = SdkMcpSession(connected)
        for key, query in SCENARIOS:
            logger.info("agent scenario %s", key)
            result = await agent.run(query, history=[], session=session)
            scenarios[key] = {
                "query": query,
                "message": result.message,
                "tool_trace": [entry.model_dump() for entry in result.tool_trace],
                "hotel_ids": hotel_ids(result),
                "sources": source_records(result),
                "comparison": result.comparison,
                "stopped_early": result.stopped_early,
            }

    return {
        "artifact_version": 1,
        "model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "data_source": "mock",
        "is_live": False,
        "doc_count": len(load_corpus(settings.rag_corpus_path)),
        "scenarios": scenarios,
    }


def main() -> None:
    payload = asyncio.run(run())
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT_PATH}")
    for key, scenario in payload["scenarios"].items():
        tools = [entry["tool"] for entry in scenario["tool_trace"]]
        print(f"{key}: tools={tools} hotels={scenario['hotel_ids']}")


if __name__ == "__main__":
    main()
