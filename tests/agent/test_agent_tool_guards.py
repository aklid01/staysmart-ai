import pytest

from staysmart.agent.tools import ToolStatus, execute_agent_tool


async def test_unknown_tool_returns_error_outcome(retriever):
    outcome = await execute_agent_tool("no_such_tool", {}, None, retriever)

    assert outcome.status is ToolStatus.ERROR
    assert "unknown tool" in outcome.payload


async def test_non_dict_arguments_return_error_outcome(retriever):
    outcome = await execute_agent_tool("search_hotels", "not-a-dict", None, retriever)

    assert outcome.status is ToolStatus.ERROR
    assert "must be an object" in outcome.payload


async def test_blank_knowledge_query_returns_error_outcome(retriever):
    outcome = await execute_agent_tool("search_knowledge", {"query": "   "}, None, retriever)

    assert outcome.status is ToolStatus.ERROR
    assert "non-empty query" in outcome.payload


async def test_transport_failure_returns_error_outcome(retriever):
    class ExplodingSession:
        async def call_tool(self, name, arguments):
            raise RuntimeError("session lost")

    outcome = await execute_agent_tool("search_hotels", {"destination": "Kyoto"}, ExplodingSession(), retriever)

    assert outcome.status is ToolStatus.ERROR
    assert "MCP session unavailable" in outcome.payload


@pytest.mark.parametrize(
    ("arguments", "fragment"),
    [
        ({}, "search_knowledge requires"),
        ({"query": ""}, "search_knowledge requires"),
        ({"query": None}, "search_knowledge requires"),
    ],
)
async def test_knowledge_query_guards_cover_empty_shapes(arguments, fragment, retriever):
    outcome = await execute_agent_tool("search_knowledge", arguments, None, retriever)

    assert outcome.status is ToolStatus.ERROR
    assert fragment in outcome.payload
