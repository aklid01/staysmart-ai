import pytest
from mcp import Client

from staysmart.agent.tools import AGENT_TOOLS, HOTEL_TOOLS
from staysmart.config import Settings
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.provider import build_provider


@pytest.fixture
def mcp_server():
    settings = Settings(log_level="WARNING")
    provider = build_provider(settings)
    return build_mcp_server(settings, provider)


def agent_tool_by_name(name):
    return next(tool for tool in AGENT_TOOLS if tool["function"]["name"] == name)


async def test_agent_hotel_tool_schemas_mirror_mcp_server_contract(mcp_server):
    async with Client(server=mcp_server) as client:
        listing = await client.list_tools()
    mcp_schemas = {tool.name: tool.input_schema for tool in listing.tools if tool.name in HOTEL_TOOLS}

    assert set(mcp_schemas) == HOTEL_TOOLS
    for name, schema in mcp_schemas.items():
        agent_schema = agent_tool_by_name(name)["function"]["parameters"]
        assert set(agent_schema["properties"]) == set(schema["properties"]), name
        assert set(agent_schema["required"]) == set(schema["required"]), name


async def test_agent_tools_cover_hotel_tools_plus_knowledge():
    names = {tool["function"]["name"] for tool in AGENT_TOOLS}

    assert names == HOTEL_TOOLS | {"search_knowledge"}
