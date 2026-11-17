from mcp import Client
from payloads import STAY_DATES

from staysmart.domain.models import (
    AvailabilityResult,
    HotelDetails,
    HotelPolicyInfo,
)


async def test_get_hotel_details_returns_room_quotes_and_policy(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "get_hotel_details",
            {"hotel_id": "hotel-lis-01", **STAY_DATES},
        )

        assert result.is_error is False
        structured = result.structured_content
        model = HotelDetails.model_validate(structured)
        assert model.data_source == "mock"
        assert [quote.room_type_id for quote in model.room_quotes] == [
            "room-lis-01-std",
            "room-lis-01-suite",
        ]
        assert structured["cancellation_policy"]["policy_type"] == "free"
        assert structured["room_quotes"][0]["total_price"] == 457.32
        assert structured["room_quotes"][1]["total_price"] is None


async def test_get_hotel_details_defaults_to_the_anchor_single_night(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("get_hotel_details", {"hotel_id": "hotel-lis-01"})

        assert result.is_error is False
        structured = result.structured_content
        assert structured["check_in"] == "2026-11-01"
        assert structured["check_out"] == "2026-11-02"
        assert structured["room_quotes"][0]["nights"] == 1


async def test_get_hotel_details_unknown_hotel_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("get_hotel_details", {"hotel_id": "hotel-xxx-99"})

        assert result.is_error is True
        assert result.content[0].text == (
            "Error executing tool get_hotel_details: unknown_hotel: Unknown hotel_id 'hotel-xxx-99' in the mock dataset"
        )


async def test_check_availability_reports_sold_out_as_a_success_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "check_availability",
            {
                "hotel_id": "hotel-van-03",
                "room_type_id": "room-van-03-std",
                **STAY_DATES,
            },
        )

        assert result.is_error is False
        structured = result.structured_content
        AvailabilityResult.model_validate(structured)
        assert structured["available"] is False
        assert structured["nights_requested"] == 3
        assert structured["nights_available"] == 0
        assert structured["sold_out_dates"] == ["2026-12-04", "2026-12-05", "2026-12-06"]
        assert structured["total_price"] is None


async def test_check_availability_partial_stay_has_no_invented_total(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "check_availability",
            {
                "hotel_id": "hotel-kyo-01",
                "room_type_id": "room-kyo-01-std",
                **STAY_DATES,
            },
        )

        assert result.is_error is False
        structured = result.structured_content
        assert structured["nights_available"] == 2
        assert structured["available"] is False
        assert structured["nights_requested"] == 3
        assert structured["total_price"] is None
        assert structured["nightly_rates"] == [252.75, 215.82]


async def test_check_availability_unknown_room_type_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "check_availability",
            {
                "hotel_id": "hotel-lis-02",
                "room_type_id": "room-lis-02-suite",
                **STAY_DATES,
            },
        )

        assert result.is_error is True
        assert result.content[0].text == (
            "Error executing tool check_availability: unknown_room_type: "
            "Unknown room_type_id 'room-lis-02-suite' for hotel 'hotel-lis-02'"
        )


async def test_get_hotel_policies_returns_grounded_policy_facts(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("get_hotel_policies", {"hotel_id": "hotel-kyo-01"})

        assert result.is_error is False
        structured = result.structured_content
        HotelPolicyInfo.model_validate(structured)
        assert structured["pet_policy"] == "allowed"
        assert structured["pet_policy_source"] == "amenities"
        assert structured["cancellation_policy"]["policy_type"] == "partial"
        assert structured["information_gaps"] == ["check_in_time", "check_out_time"]
        assert structured["check_in_time"] is None
        assert structured["data_source"] == "mock"


async def test_get_hotel_policies_unknown_hotel_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("get_hotel_policies", {"hotel_id": "hotel-xxx-99"})

        assert result.is_error is True
        assert result.content[0].text == (
            "Error executing tool get_hotel_policies: unknown_hotel: "
            "Unknown hotel_id 'hotel-xxx-99' in the mock dataset"
        )
