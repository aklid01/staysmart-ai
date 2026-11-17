import pytest
from mcp import Client
from payloads import STAY_DATES
from pydantic import ValidationError

from staysmart.domain.models import (
    AvailabilityResult,
    HotelComparison,
    HotelDetails,
    HotelPolicyInfo,
    HotelSearchResult,
)
from staysmart.mcp_server.server import build_mcp_server


async def test_compare_hotels_reports_unresolved_ids_and_rows(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "compare_hotels",
            {
                "hotel_ids": ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"],
                "preferences": ["river view"],
                **STAY_DATES,
            },
        )

        assert result.is_error is False
        structured = result.structured_content
        HotelComparison.model_validate(structured)
        assert [row["hotel_id"] for row in structured["rows"]] == ["hotel-lis-01", "hotel-lis-02"]
        assert structured["rows"][0]["nightly_price"] == 152.44
        assert structured["rows"][0]["total_stay_price"] == 457.32
        assert structured["rows"][1]["total_stay_price"] is None
        assert structured["unresolved_hotel_ids"] == ["hotel-xxx-99"]
        assert structured["unmet_preferences"] == ["preference_not_verified:river view"]
        assert structured["data_source"] == "mock"


async def test_compare_hotels_rejects_an_empty_id_list(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "compare_hotels",
            {"hotel_ids": [], **STAY_DATES},
        )

        assert result.is_error is True
        assert result.content[0].text == (
            "Error executing tool compare_hotels: invalid_argument: hotel_ids must contain at least one hotel id"
        )


class ExplodingProvider:
    async def search(self, query):
        raise RuntimeError("boom")

    async def get_hotel_details(self, hotel_id, **kwargs):
        raise RuntimeError("boom")

    async def check_availability(self, hotel_id, room_type_id, check_in, check_out, **kwargs):
        raise RuntimeError("boom")


async def test_unexpected_provider_crash_returns_the_generic_error(settings):
    exploding = ExplodingProvider()
    server = build_mcp_server(settings, exploding)
    async with Client(server=server) as client:
        result = await client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", **STAY_DATES},
        )

        assert result.is_error is True
        assert result.content[0].text == "Error executing tool search_hotels"
        assert "boom" not in result.content[0].text


async def test_tool_results_validate_against_domain_models(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        search = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Vancouver", **STAY_DATES},
        )
        details = await mcp_client.call_tool(
            "get_hotel_details",
            {"hotel_id": "hotel-van-03", **STAY_DATES},
        )
        availability = await mcp_client.call_tool(
            "check_availability",
            {
                "hotel_id": "hotel-van-03",
                "room_type_id": "room-van-03-std",
                **STAY_DATES,
            },
        )
        policies = await mcp_client.call_tool("get_hotel_policies", {"hotel_id": "hotel-van-03"})

        HotelSearchResult.model_validate(search.structured_content)
        HotelDetails.model_validate(details.structured_content)
        AvailabilityResult.model_validate(availability.structured_content)
        HotelPolicyInfo.model_validate(policies.structured_content)

        with pytest.raises(ValidationError):
            HotelSearchResult.model_validate({"data_source": "live"})
