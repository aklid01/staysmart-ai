import asyncio
import logging
from typing import Any

from demo_summaries import write_artifact
from mcp import Client

from staysmart.agent.agent import HotelAgent
from staysmart.agent.llm import OpenAICompatLLM
from staysmart.config import PROJECT_ROOT, Settings, configure_logging
from staysmart.mcp_client import SdkMcpSession
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.provider import build_provider
from staysmart.rag.bootstrap import build_project_index
from staysmart.rag.corpus import load_corpus
from staysmart.rag.embedder import FastEmbedEmbedder
from staysmart.rag.service import RagRetriever

logger = logging.getLogger("staysmart")

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "agent_demo.json"

SCENARIOS = [
    (
        "search_kyoto",
        "Find hotels in Kyoto for two guests from December 4 to 7, 2026, "
        "under 250 USD per night, with wifi and breakfast.",
    ),
    (
        "policy_kyoto",
        "Can I bring my dog to Gion Machiya Stay? And what time is check-in in Kyoto?",
    ),
    (
        "compare_lisbon",
        "Compare Alfama Riverside Boutique and Baixa Central Hotel for December 4-7, 2026 "
        "and recommend one for a budget traveller.",
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


async def run() -> dict[str, Any]:
    settings = Settings(log_level="WARNING")
    configure_logging(settings.log_level)

    embedder = FastEmbedEmbedder(settings.rag_model)
    if not settings.rag_index_path.exists():
        build_project_index(settings, embedder)
    retriever = RagRetriever.load(settings.rag_index_path, embedder)

    provider = build_provider(settings)
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
                "outcome": result.outcome.value,
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
    write_artifact(ARTIFACT_PATH, payload)
    for key, scenario in payload["scenarios"].items():
        tools = [entry["tool"] for entry in scenario["tool_trace"]]
        print(f"{key}: tools={tools} hotels={scenario['hotel_ids']}")


if __name__ == "__main__":
    main()
