import asyncio
import threading
import time
from typing import Any

import httpx
import uvicorn
from demo_summaries import (
    availability_summary,
    comparison_summary,
    details_summary,
    policies_summary,
    search_summary,
    write_artifact,
)
from starlette.applications import Starlette

from staysmart.agent.llm import LLMCompletion, ScriptedLLM
from staysmart.app.main import APP_NAME, create_app
from staysmart.config import PROJECT_ROOT, Settings, configure_logging
from staysmart.mcp_server.server import SERVER_NAME

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "api_demo.json"
STAY_DATES = {"check_in": "2026-12-04", "check_out": "2026-12-07"}


def record(client: httpx.Client, method: str, path: str, **kwargs) -> dict[str, Any]:
    response = client.request(method, path, **kwargs)
    return {
        "method": method,
        "path": path,
        "status": response.status_code,
        "body": response.json(),
    }


def summarized(recorded: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": recorded["method"],
        "path": recorded["path"],
        "status": recorded["status"],
        "body": summary,
    }


def start_server(app: Starlette) -> tuple[uvicorn.Server, threading.Thread, int]:
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("uvicorn server did not start in time")
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, port


async def run() -> dict[str, Any]:
    settings = Settings(log_level="WARNING")
    configure_logging(settings.log_level)
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=(
                    "This API demo records a scripted model reply so the artifact stays "
                    "deterministic; the real agent demo lives in scripts/demo_agent.py."
                ),
                tool_calls=[],
            )
        ]
    )
    app = create_app(settings, llm=llm)

    server, thread, port = start_server(app)
    try:
        base_url = f"http://127.0.0.1:{port}"
        with httpx.Client(base_url=base_url, timeout=30) as client:
            health = record(client, "GET", "/api/health")

            search_kyoto = record(
                client,
                "POST",
                "/api/search",
                json={
                    "destination": "Kyoto",
                    **STAY_DATES,
                    "guests": 2,
                    "rooms": 1,
                    "max_nightly_budget": 250.0,
                    "min_rating": 8.0,
                    "amenities": ["WIFI", "BREAKFAST"],
                    "preferences": ["quiet room"],
                },
            )
            search_lisbon = record(
                client,
                "POST",
                "/api/search",
                json={
                    "destination": "Lisbon",
                    **STAY_DATES,
                    "max_nightly_budget": 160.0,
                    "min_rating": 7.0,
                    "amenities": ["WIFI"],
                },
            )
            details = record(
                client,
                "GET",
                "/api/hotels/hotel-lis-01",
                params={"check_in": "2026-12-04", "check_out": "2026-12-07", "rooms": 1, "guests": 2},
            )
            availability = record(
                client,
                "POST",
                "/api/hotels/hotel-van-03/availability",
                json={"room_type_id": "room-van-03-std", **STAY_DATES, "rooms": 1},
            )
            compare_ids = ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"]
            comparison = record(
                client,
                "POST",
                "/api/compare",
                json={
                    "hotel_ids": compare_ids,
                    **STAY_DATES,
                    "rooms": 1,
                    "guests": 2,
                    "preferences": ["river view"],
                },
            )
            policies_kyo = record(client, "GET", "/api/hotels/hotel-kyo-01/policies")
            policies_lis = record(client, "GET", "/api/hotels/hotel-lis-01/policies")
            chat_agent = record(
                client,
                "POST",
                "/api/chat",
                json={
                    "message": "Find a hotel in Kyoto for two guests in December.",
                    "conversation_id": "demo-conversation",
                },
            )

            errors = {
                "unknown_destination_search": record(
                    client, "POST", "/api/search", json={"destination": "Atlantis", **STAY_DATES}
                ),
                "unknown_hotel_details": record(client, "GET", "/api/hotels/hotel-xxx-99"),
                "invalid_dates_availability": record(
                    client,
                    "POST",
                    "/api/hotels/hotel-lis-02/availability",
                    json={
                        "room_type_id": "room-lis-02-std",
                        "check_in": "2026-12-07",
                        "check_out": "2026-12-04",
                    },
                ),
                "empty_compare_hotel_ids": record(client, "POST", "/api/compare", json={"hotel_ids": [], **STAY_DATES}),
                "validation_missing_destination": record(client, "POST", "/api/search", json=STAY_DATES),
                "chat_empty_message": record(client, "POST", "/api/chat", json={"message": ""}),
            }
    finally:
        server.should_exit = True
        thread.join(timeout=30)

    return {
        "artifact_version": 1,
        "service": APP_NAME,
        "server_name": SERVER_NAME,
        "transport": "stdio",
        "currency": settings.currency,
        "data_source": "mock",
        "is_live": False,
        "base_url": "http://127.0.0.1",
        "requests": {
            "health": health,
            "search_kyoto_family": summarized(search_kyoto, search_summary(search_kyoto["body"])),
            "search_lisbon_budget": summarized(search_lisbon, search_summary(search_lisbon["body"])),
            "details_lis_01": summarized(details, details_summary(details["body"])),
            "availability_van_03": summarized(availability, availability_summary(availability["body"], rooms=1)),
            "compare_lisbon": summarized(comparison, comparison_summary(comparison["body"], compare_ids)),
            "policies_kyo_01": summarized(policies_kyo, policies_summary(policies_kyo["body"])),
            "policies_lis_01": summarized(policies_lis, policies_summary(policies_lis["body"])),
            "chat_agent": chat_agent,
        },
        "errors": errors,
    }


def main() -> None:
    payload = asyncio.run(run())
    write_artifact(ARTIFACT_PATH, payload)
    statuses = {key: record["status"] for key, record in {**payload["requests"], **payload["errors"]}.items()}
    print(f"statuses={statuses}")


if __name__ == "__main__":
    main()
