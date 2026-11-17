import asyncio
from typing import Any

from demo_summaries import (
    availability_summary,
    comparison_summary,
    details_summary,
    policies_summary,
    search_summary,
    write_artifact,
)
from mcp import Client

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.mcp_server.server import SERVER_NAME, build_mcp_server
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import build_provider

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "mcp_demo.json"
CHECK_IN = "2026-12-04"
CHECK_OUT = "2026-12-07"


def error_record(result: Any) -> dict[str, Any]:
    return {"is_error": result.is_error, "message": result.content[0].text}


async def call_tool(client: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(name, arguments)
    if result.is_error:
        raise RuntimeError(f"{name} failed: {result.content[0].text}")
    return result.structured_content


async def run() -> None:
    settings = Settings()
    provider = build_provider(settings)
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
            "availability_van_03": availability_summary(availability, rooms=1),
            "compare_lisbon": comparison_summary(comparison, compare_ids),
            "policies_kyo_01": policies_summary(policies_kyo),
            "policies_lis_01": policies_summary(policies_lis),
        },
        "errors": errors,
    }

    write_artifact(ARTIFACT_PATH, payload)
    print(f"tools_listed={len(tools_listed)} compare_rows={len(comparison['rows'])}")


if __name__ == "__main__":
    asyncio.run(run())
