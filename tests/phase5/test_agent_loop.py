import json

import pytest
from mcp import Client

from staysmart.agent.agent import HotelAgent
from staysmart.agent.llm import LLMCompletion, LLMToolCall, ScriptedLLM
from staysmart.app.mcp_client import SdkMcpSession

KYOTO_SEARCH_ARGS = {
    "destination": "Kyoto",
    "check_in": "2026-12-04",
    "check_out": "2026-12-07",
    "guests": 2,
    "rooms": 1,
}


async def run_agent(llm, mcp_server, retriever, message="Find hotels in Kyoto", history=None):
    agent = HotelAgent(llm, retriever)
    async with Client(server=mcp_server) as connected:
        session = SdkMcpSession(connected)
        return await agent.run(message, history=history or [], session=session)


async def test_search_tool_call_then_grounded_answer(mcp_server, retriever):
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_hotels", arguments=KYOTO_SEARCH_ARGS)],
            ),
            LLMCompletion(content="Gion Machiya Stay is the only Kyoto hotel under 250 USD with those amenities.", tool_calls=[]),
        ]
    )

    result = await run_agent(llm, mcp_server, retriever)

    assert result.message.startswith("Gion Machiya Stay")
    assert result.stopped_early is False
    assert [entry.model_dump() for entry in result.tool_trace] == [
        {"tool": "search_hotels", "status": "ok"}
    ]
    assert {entry["hotel"]["hotel_id"] for entry in result.hotels} == {
        "hotel-kyo-01",
        "hotel-kyo-02",
        "hotel-kyo-03",
    }
    kyo = next(entry for entry in result.hotels if entry["hotel"]["hotel_id"] == "hotel-kyo-01")
    assert kyo["quote"]["sold_out_dates"] == ["2026-12-05"]
    assert kyo["quote"]["data_source"] == "mock"

    second_request = llm.requests[1]["messages"]
    system, user, assistant, tool = second_request
    assert system["role"] == "system"
    assert "mock" in system["content"].lower()
    assert user["content"] == "Find hotels in Kyoto"
    assert assistant["tool_calls"][0]["function"]["name"] == "search_hotels"
    payload = json.loads(tool["content"])
    assert payload["total_found"] == 3
    assert tool["tool_call_id"] == "call-1"


async def test_tool_error_fed_back_then_recovered(mcp_server, retriever):
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_hotels", arguments={"destination": "Atlantis", "check_in": "2026-12-04", "check_out": "2026-12-07"})],
            ),
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-2", name="search_hotels", arguments=KYOTO_SEARCH_ARGS)],
            ),
            LLMCompletion(content="Kyoto is available; Atlantis is not in the dataset.", tool_calls=[]),
        ]
    )

    result = await run_agent(llm, mcp_server, retriever)

    assert [entry.model_dump() for entry in result.tool_trace] == [
        {"tool": "search_hotels", "status": "error"},
        {"tool": "search_hotels", "status": "ok"},
    ]
    error_message = llm.requests[1]["messages"][-1]["content"]
    assert error_message.startswith("Error:")
    assert "No destination matches 'Atlantis'" in error_message
    assert "hotel-kyo-01" in {entry["hotel"]["hotel_id"] for entry in result.hotels}


async def test_duplicate_call_rejected_without_execution(mcp_server, retriever):
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_hotels", arguments=KYOTO_SEARCH_ARGS)],
            ),
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-2", name="search_hotels", arguments=dict(KYOTO_SEARCH_ARGS))],
            ),
            LLMCompletion(content="Done.", tool_calls=[]),
        ]
    )

    result = await run_agent(llm, mcp_server, retriever)

    assert [entry.model_dump() for entry in result.tool_trace] == [
        {"tool": "search_hotels", "status": "ok"},
        {"tool": "search_hotels", "status": "duplicate"},
    ]
    duplicate_message = llm.requests[2]["messages"][-1]["content"]
    assert "already called" in duplicate_message


async def test_turn_limit_stops_tool_loops_with_forced_summary(mcp_server, retriever):
    calls = [
        LLMCompletion(
            content=None,
            tool_calls=[
                LLMToolCall(
                    id=f"call-{i}",
                    name="search_hotels",
                    arguments={
                        "destination": "Kyoto",
                        "check_in": "2026-12-04",
                        "check_out": "2026-12-07",
                        "guests": 2,
                        "rooms": 1,
                        "preferences": [f"preference-{i}"],
                    },
                )
            ],
        )
        for i in range(6)
    ]
    llm = ScriptedLLM([*calls, LLMCompletion(content="Forced summary of findings.", tool_calls=[])])

    result = await run_agent(llm, mcp_server, retriever)

    assert result.stopped_early is True
    assert result.message == "Forced summary of findings."
    assert llm.completed_calls == 7
    assert sum(entry.status == "ok" for entry in result.tool_trace) == 6
    summary_request = llm.requests[-1]
    assert summary_request["tools"] is None
    assert "summarize" in summary_request["messages"][-1]["content"].lower()


async def test_tool_budget_limits_executed_calls(mcp_server, retriever):
    date_pairs = [(4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (12, 13), (13, 14), (14, 15), (15, 16)]
    completions = []
    call_index = 0
    for _turn in range(4):
        calls = [
            LLMToolCall(
                id=f"call-{call_index + offset}",
                name="get_hotel_details",
                arguments={
                    "hotel_id": "hotel-lis-01",
                    "check_in": f"2026-12-{date_pairs[call_index + offset][0]:02d}",
                    "check_out": f"2026-12-{date_pairs[call_index + offset][1]:02d}",
                },
            )
            for offset in range(3)
        ]
        completions.append(LLMCompletion(content=None, tool_calls=calls))
        call_index += 3
    llm = ScriptedLLM([*completions, LLMCompletion(content="Budget summary.", tool_calls=[])])

    result = await run_agent(llm, mcp_server, retriever)

    assert result.stopped_early is True
    assert sum(entry.status == "ok" for entry in result.tool_trace) == 12
    assert llm.completed_calls == 5


async def test_search_knowledge_collects_sources(mcp_server, retriever):
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_knowledge", arguments={"query": "Are dogs and cats allowed at the townhouse?", "hotel_id": "hotel-kyo-01", "category": "pet_policy"})],
            ),
            LLMCompletion(content="Pets are allowed at Gion Machiya Stay [Gion Machiya Stay pet policy].", tool_calls=[]),
        ]
    )

    result = await run_agent(llm, mcp_server, retriever)

    assert [entry.model_dump() for entry in result.tool_trace] == [
        {"tool": "search_knowledge", "status": "ok"}
    ]
    assert result.sources
    assert "hotel-kyo-01-pet-policy" in {source.doc_id for source in result.sources}
    knowledge_message = llm.requests[1]["messages"][-1]["content"]
    payload = json.loads(knowledge_message)
    assert "formatted_context" in payload
    assert payload["sources"]


async def test_search_and_details_dedupe_to_details_form(mcp_server, retriever):
    llm = ScriptedLLM(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_hotels", arguments=KYOTO_SEARCH_ARGS)],
            ),
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-2", name="get_hotel_details", arguments={"hotel_id": "hotel-kyo-01", "check_in": "2026-12-04", "check_out": "2026-12-07"})],
            ),
            LLMCompletion(content="Here are the details.", tool_calls=[]),
        ]
    )

    result = await run_agent(llm, mcp_server, retriever)

    assert len(result.hotels) == 3
    entry = next(item for item in result.hotels if item["hotel"]["hotel_id"] == "hotel-kyo-01")
    assert entry["hotel"]["hotel_id"] == "hotel-kyo-01"
    assert "room_quotes" in entry


async def test_history_passes_through_and_conversation_id_generated(mcp_server, retriever):
    llm = ScriptedLLM([LLMCompletion(content="Hello again.", tool_calls=[])])

    result = await run_agent(
        llm,
        mcp_server,
        retriever,
        message="Any spa hotels?",
        history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    )

    messages = llm.requests[0]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert result.conversation_id
    assert len(result.conversation_id) >= 8


async def test_model_producing_nothing_twice_raises(mcp_server, retriever):
    llm = ScriptedLLM([LLMCompletion(content=None, tool_calls=[]), LLMCompletion(content=None, tool_calls=[])])

    agent = HotelAgent(llm, retriever)
    async with Client(server=mcp_server) as session:
        with pytest.raises(Exception, match="did not produce"):
            await agent.run("hello", history=[], session=session)
