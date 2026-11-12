import json
import threading
import time

import httpx
import uvicorn

from staysmart.agent.llm import LLMCompletion, ScriptedLLM
from staysmart.app.main import APP_NAME, create_app
from staysmart.config import PROJECT_ROOT, Settings, configure_logging
from staysmart.mcp_server.server import SERVER_NAME

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "api_demo.json"
STAY_DATES = {"check_in": "2026-12-04", "check_out": "2026-12-07"}


def quote_summary(quote: dict) -> dict:
    return {
        "room_type_id": quote["room_type_id"],
        "nights": quote["nights"],
        "nights_available": quote["nights_available"],
        "nightly_rates": quote["nightly_rates"],
        "avg_nightly_rate": quote["avg_nightly_rate"],
        "total_price": quote["total_price"],
        "available": quote["available"],
        "partially_available": quote["partially_available"],
        "sold_out_dates": quote["sold_out_dates"],
    }


def hit_summary(hit: dict) -> dict:
    hotel = hit["hotel"]
    quote = hit["quote"]
    return {
        "hotel_id": hotel["hotel_id"],
        "hotel_name": hotel["name"],
        "location": hotel["location"],
        "guest_rating": hotel["guest_rating"],
        "star_rating": hotel["star_rating"],
        "amenities": hotel["amenities"],
        "matched_amenities": hit["matched_amenities"],
        "cancellation_policy": hotel["cancellation_policy"]["policy_type"],
        "refundable": hotel["cancellation_policy"]["refundable"],
        "room_type_id": quote["room_type_id"],
        "nights": quote["nights"],
        "nights_available": quote["nights_available"],
        "nightly_rates": quote["nightly_rates"],
        "avg_nightly_rate": quote["avg_nightly_rate"],
        "total_price": quote["total_price"],
        "available": quote["available"],
        "partially_available": quote["partially_available"],
        "sold_out_dates": quote["sold_out_dates"],
        "currency": quote["currency"],
        "data_source": quote["data_source"],
        "is_live": quote["is_live"],
    }


def search_summary(structured: dict) -> dict:
    return {
        "destination": structured["query"]["destination"],
        "check_in": structured["query"]["check_in"],
        "check_out": structured["query"]["check_out"],
        "guests": structured["query"]["guests"],
        "rooms": structured["query"]["rooms"],
        "max_nightly_budget": structured["query"]["max_nightly_budget"],
        "min_rating": structured["query"]["min_rating"],
        "required_amenities": structured["query"]["amenities"],
        "preferences": structured["query"]["preferences"],
        "total_found": structured["total_found"],
        "hotel_ids": [hit["hotel"]["hotel_id"] for hit in structured["results"]],
        "unmet_preferences": structured["unmet_preferences"],
        "hits": [hit_summary(hit) for hit in structured["results"]],
    }


def details_summary(structured: dict) -> dict:
    policy = structured["cancellation_policy"]
    return {
        "hotel_id": structured["hotel"]["hotel_id"],
        "hotel_name": structured["hotel"]["name"],
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": structured["rooms"],
        "guests": structured["guests"],
        "currency": structured["currency"],
        "cancellation_policy": policy["policy_type"],
        "refundable": policy["refundable"],
        "free_cancellation_days": policy["free_cancellation_days"],
        "penalty_nights": policy["penalty_nights"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "room_quotes": [quote_summary(quote) for quote in structured["room_quotes"]],
    }


def availability_summary(structured: dict, rooms: int) -> dict:
    return {
        "hotel_id": structured["hotel_id"],
        "room_type_id": structured["room_type_id"],
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": rooms,
        "currency": structured["currency"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "nights_requested": structured["nights_requested"],
        "nights_available": structured["nights_available"],
        "available": structured["available"],
        "sold_out_dates": structured["sold_out_dates"],
        "nightly_rates": structured["nightly_rates"],
        "total_price": structured["total_price"],
    }


def row_summary(row: dict) -> dict:
    return {
        "hotel_id": row["hotel_id"],
        "name": row["name"],
        "location": row["location"],
        "guest_rating": row["guest_rating"],
        "amenities": row["amenities"],
        "cancellation_policy": row["cancellation_policy"],
        "refundable": row["refundable"],
        "nightly_price": row["nightly_price"],
        "total_stay_price": row["total_stay_price"],
        "availability": row["availability"],
    }


def comparison_summary(structured: dict, requested_ids: list[str]) -> dict:
    return {
        "hotel_ids_requested": requested_ids,
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": structured["rooms"],
        "guests": structured["guests"],
        "currency": structured["currency"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "rows": [row_summary(row) for row in structured["rows"]],
        "unresolved_hotel_ids": structured["unresolved_hotel_ids"],
        "unmet_preferences": structured["unmet_preferences"],
    }


def policies_summary(structured: dict) -> dict:
    policy = structured["cancellation_policy"]
    return {
        "hotel_id": structured["hotel_id"],
        "hotel_name": structured["hotel_name"],
        "general_info": structured["general_info"],
        "cancellation_policy": policy["policy_type"],
        "refundable": policy["refundable"],
        "free_cancellation_days": policy["free_cancellation_days"],
        "penalty_nights": policy["penalty_nights"],
        "policy_description": policy["description"],
        "pet_policy": structured["pet_policy"],
        "pet_policy_source": structured["pet_policy_source"],
        "check_in_time": structured["check_in_time"],
        "check_out_time": structured["check_out_time"],
        "information_gaps": structured["information_gaps"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
    }


def record(client: httpx.Client, method: str, path: str, **kwargs) -> dict:
    response = client.request(method, path, **kwargs)
    return {
        "method": method,
        "path": path,
        "status": response.status_code,
        "body": response.json(),
    }


def summarized(recorded: dict, summary: dict) -> dict:
    return {
        "method": recorded["method"],
        "path": recorded["path"],
        "status": recorded["status"],
        "body": summary,
    }


def start_server(app):
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


async def run() -> dict:
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
    import asyncio

    payload = asyncio.run(run())
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT_PATH}")
    statuses = {key: record["status"] for key, record in {**payload["requests"], **payload["errors"]}.items()}
    print(f"statuses={statuses}")


if __name__ == "__main__":
    main()
