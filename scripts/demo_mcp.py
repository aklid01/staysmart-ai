import asyncio
import json

from mcp import Client

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.mcp_server.server import SERVER_NAME, build_mcp_server
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import get_provider

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "mcp_demo.json"
CHECK_IN = "2026-12-04"
CHECK_OUT = "2026-12-07"


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
    query = structured["query"]
    return {
        "destination": query["destination"],
        "check_in": query["check_in"],
        "check_out": query["check_out"],
        "guests": query["guests"],
        "rooms": query["rooms"],
        "max_nightly_budget": query["max_nightly_budget"],
        "min_rating": query["min_rating"],
        "required_amenities": query["amenities"],
        "preferences": query["preferences"],
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


def availability_summary(structured: dict) -> dict:
    return {
        "hotel_id": structured["hotel_id"],
        "room_type_id": structured["room_type_id"],
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": 1,
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


def error_record(result) -> dict:
    return {"is_error": result.is_error, "message": result.content[0].text}


async def call_tool(client, name: str, arguments: dict) -> dict:
    result = await client.call_tool(name, arguments)
    if result.is_error:
        raise RuntimeError(f"{name} failed: {result.content[0].text}")
    return result.structured_content


async def run() -> None:
    settings = Settings()
    provider = get_provider(settings)
    dataset = load_dataset(settings.dataset_path)
    server = build_mcp_server(settings, provider)

    async with Client(server=server) as client:
        listing = await client.list_tools()
        tools_listed = sorted(tool.name for tool in listing.tools)

        search_kyoto = await call_tool(
            client,
            "search_hotels",
            {
                "destination": "Kyoto",
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
                "guests": 2,
                "rooms": 1,
                "max_nightly_budget": 250.0,
                "min_rating": 8.0,
                "amenities": ["WIFI", "BREAKFAST"],
                "preferences": ["quiet room"],
            },
        )
        search_lisbon = await call_tool(
            client,
            "search_hotels",
            {
                "destination": "Lisbon",
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
                "guests": 2,
                "rooms": 1,
                "max_nightly_budget": 160.0,
                "min_rating": 7.0,
                "amenities": ["WIFI"],
            },
        )
        details = await call_tool(
            client,
            "get_hotel_details",
            {
                "hotel_id": "hotel-lis-01",
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
                "rooms": 1,
                "guests": 2,
            },
        )
        availability = await call_tool(
            client,
            "check_availability",
            {
                "hotel_id": "hotel-van-03",
                "room_type_id": "room-van-03-std",
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
                "rooms": 1,
            },
        )
        compare_ids = ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"]
        comparison = await call_tool(
            client,
            "compare_hotels",
            {
                "hotel_ids": compare_ids,
                "check_in": CHECK_IN,
                "check_out": CHECK_OUT,
                "rooms": 1,
                "guests": 2,
                "preferences": ["river view"],
            },
        )
        policies_kyo = await call_tool(client, "get_hotel_policies", {"hotel_id": "hotel-kyo-01"})
        policies_lis = await call_tool(client, "get_hotel_policies", {"hotel_id": "hotel-lis-01"})

        errors = {}
        for key, name, arguments in [
            (
                "unknown_destination_search",
                "search_hotels",
                {"destination": "Atlantis", "check_in": CHECK_IN, "check_out": CHECK_OUT},
            ),
            ("unknown_hotel_details", "get_hotel_details", {"hotel_id": "hotel-xxx-99"}),
            (
                "invalid_dates_availability",
                "check_availability",
                {
                    "hotel_id": "hotel-lis-02",
                    "room_type_id": "room-lis-02-std",
                    "check_in": "2026-12-07",
                    "check_out": "2026-12-04",
                },
            ),
        ]:
            result = await client.call_tool(name, arguments)
            errors[key] = error_record(result)

    payload = {
        "artifact_version": 1,
        "server_name": SERVER_NAME,
        "transport": "in-process",
        "currency": settings.currency,
        "data_source": "mock",
        "is_live": False,
        "dataset_schema_version": dataset.schema_version,
        "tools_listed": tools_listed,
        "results": {
            "search_kyoto_family": search_summary(search_kyoto),
            "search_lisbon_budget": search_summary(search_lisbon),
            "details_lis_01": details_summary(details),
            "availability_van_03": availability_summary(availability),
            "compare_lisbon": comparison_summary(comparison, compare_ids),
            "policies_kyo_01": policies_summary(policies_kyo),
            "policies_lis_01": policies_summary(policies_lis),
        },
        "errors": errors,
    }

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {ARTIFACT_PATH}")
    print(f"tools_listed={len(tools_listed)} compare_rows={len(comparison['rows'])}")


if __name__ == "__main__":
    asyncio.run(run())
