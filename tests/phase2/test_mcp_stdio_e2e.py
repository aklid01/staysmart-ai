import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[2]

TOOL_NAMES = {
    "search_hotels",
    "get_hotel_details",
    "check_availability",
    "compare_hotels",
    "get_hotel_policies",
}


def stdio_params():
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "staysmart.mcp_server"],
        cwd=str(ROOT),
        env={
            "STAYSMART_LOG_LEVEL": "WARNING",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        },
    )


async def test_stdio_subprocess_completes_handshake_and_lists_five_tools():
    async with Client(server=stdio_params()) as client:
        listing = await client.list_tools()

        assert {tool.name for tool in listing.tools} == TOOL_NAMES


async def test_stdio_subprocess_returns_mock_marked_search_results():
    async with Client(server=stdio_params()) as client:
        result = await client.call_tool(
            "search_hotels",
            {
                "destination": "Kyoto",
                "check_in": "2026-12-04",
                "check_out": "2026-12-07",
                "max_nightly_budget": 250.0,
                "min_rating": 8.0,
            },
        )

        assert result.is_error is False
        structured = result.structured_content
        assert structured["data_source"] == "mock"
        assert structured["is_live"] is False
        assert structured["total_found"] == 1
        assert structured["results"][0]["hotel"]["hotel_id"] == "hotel-kyo-01"


async def test_stdio_subprocess_carries_error_results_without_failing():
    async with Client(server=stdio_params()) as client:
        result = await client.call_tool(
            "get_hotel_details",
            {"hotel_id": "hotel-xxx-99"},
        )

        assert result.is_error is True
        assert result.content[0].text == "Unknown hotel_id 'hotel-xxx-99' in the mock dataset"
