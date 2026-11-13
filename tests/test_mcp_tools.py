import pytest
from mcp import Client
from pydantic import ValidationError

from staysmart.domain.models import (
    AvailabilityResult,
    HotelComparison,
    HotelDetails,
    HotelPolicyInfo,
    HotelSearchResult,
)
from staysmart.mcp_server.server import build_mcp_server

TOOL_NAMES = {
    "search_hotels",
    "get_hotel_details",
    "check_availability",
    "compare_hotels",
    "get_hotel_policies",
}

KYOTO_SEARCH_ARGS = {
    "destination": "Kyoto",
    "check_in": "2026-12-04",
    "check_out": "2026-12-07",
    "guests": 2,
    "rooms": 1,
    "max_nightly_budget": 250.0,
    "min_rating": 8.0,
    "amenities": ["WIFI", "BREAKFAST"],
    "preferences": ["quiet room"],
}

STAY_DATES = {"check_in": "2026-12-04", "check_out": "2026-12-07"}


async def test_list_tools_returns_exactly_the_five_contract_tools(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.list_tools()

        assert {tool.name for tool in result.tools} == TOOL_NAMES


async def test_every_tool_has_a_description_and_input_schema(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.list_tools()

        for tool in result.tools:
            assert tool.description
            assert tool.input_schema.get("type") == "object"
            assert tool.input_schema.get("properties")


async def test_search_tools_do_not_expose_a_currency_argument(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.list_tools()

        schemas = {tool.name: tool.input_schema for tool in result.tools}
        assert "currency" not in schemas["search_hotels"]["properties"]
        assert "currency" not in schemas["compare_hotels"]["properties"]
        assert "currency" not in schemas["check_availability"]["properties"]


async def test_server_instructions_disclose_mock_data(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        instructions = mcp_client.session.instructions or ""

        assert "mock" in instructions.lower()


async def test_search_hotels_returns_mock_marked_structured_results(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("search_hotels", KYOTO_SEARCH_ARGS)

        assert result.is_error is False
        structured = result.structured_content
        model = HotelSearchResult.model_validate(structured)
        assert model.data_source == "mock"
        assert model.is_live is False
        assert structured["query"]["currency"] == "USD"
        assert structured["total_found"] == 1
        assert structured["results"][0]["hotel"]["hotel_id"] == "hotel-kyo-01"
        assert structured["results"][0]["quote"]["avg_nightly_rate"] == 234.28
        assert structured["results"][0]["quote"]["total_price"] is None
        assert structured["results"][0]["quote"]["sold_out_dates"] == ["2026-12-05"]
        assert structured["unmet_preferences"] == ["preference_not_verified:quiet room"]


async def test_search_hotels_accepts_minimal_arguments(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", **STAY_DATES},
        )

        assert result.is_error is False
        assert result.structured_content["total_found"] == 4


async def test_search_hotels_empty_result_set_is_a_success(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", "max_nightly_budget": 1.0, **STAY_DATES},
        )

        assert result.is_error is False
        structured = result.structured_content
        assert structured["total_found"] == 0
        assert structured["results"] == []
        assert structured["unmet_preferences"] == [
            "no_hotels_matched:Lisbon",
            "filter:max_nightly_budget=1.0",
        ]


async def test_search_hotels_unknown_destination_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Atlantis", **STAY_DATES},
        )

        assert result.is_error is True
        assert result.structured_content is None
        assert result.content[0].text == (
            "Error executing tool search_hotels: unknown_destination: "
            "No destination matches 'Atlantis' in the mock dataset"
        )


async def test_search_hotels_reversed_dates_are_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", "check_in": "2026-12-07", "check_out": "2026-12-04"},
        )

        assert result.is_error is True
        assert result.content[0].text == (
            "Error executing tool search_hotels: invalid_date: check_out must be after check_in"
        )


async def test_search_hotels_dates_beyond_the_window_are_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", "check_in": "2027-11-01", "check_out": "2027-11-03"},
        )

        assert result.is_error is True
        assert "outside the mock dataset window" in result.content[0].text


async def test_search_hotels_unknown_amenity_value_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", "amenities": ["TELEPORT"], **STAY_DATES},
        )

        assert result.is_error is True


async def test_search_hotels_missing_required_argument_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool("search_hotels", {"destination": "Lisbon"})

        assert result.is_error is True


async def test_search_hotels_non_iso_date_is_an_error_result(mcp_server):
    async with Client(server=mcp_server) as mcp_client:
        result = await mcp_client.call_tool(
            "search_hotels",
            {"destination": "Lisbon", "check_in": "not-a-date", "check_out": "2026-12-07"},
        )

        assert result.is_error is True


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
            "Error executing tool compare_hotels: hotel_ids must contain at least one hotel id"
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
