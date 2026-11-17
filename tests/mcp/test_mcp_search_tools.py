from mcp import Client
from payloads import KYOTO_SEARCH_ARGS, STAY_DATES, TOOL_NAMES

from staysmart.domain.models import (
    HotelSearchResult,
)


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
