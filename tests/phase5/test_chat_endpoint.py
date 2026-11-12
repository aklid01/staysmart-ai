import pytest
from starlette.testclient import TestClient

from staysmart.agent.errors import LLMUnavailableError
from staysmart.agent.llm import LLMCompletion, LLMToolCall, ScriptedLLM
from staysmart.app.main import create_app
from staysmart.app.mcp_client import InProcessMcpConnector


def test_chat_returns_structured_response(client, agent_llm):
    agent_llm.steps.extend(
        [
            LLMCompletion(
                content=None,
                tool_calls=[LLMToolCall(id="call-1", name="search_hotels", arguments={"destination": "Kyoto", "check_in": "2026-12-04", "check_out": "2026-12-07"})],
            ),
            LLMCompletion(content="Gion Machiya Stay is the pick.", tool_calls=[]),
        ]
    )

    response = client.post(
        "/api/chat",
        json={"message": "Find hotels in Kyoto", "conversation_id": "conv-42"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Gion Machiya Stay is the pick."
    assert body["conversation_id"] == "conv-42"
    assert body["stopped_early"] is False
    assert body["tool_trace"] == [{"tool": "search_hotels", "status": "ok"}]
    assert "hotel-kyo-01" in {entry["hotel"]["hotel_id"] for entry in body["hotels"]}
    assert body["comparison"] is None
    assert body["sources"] == []


def test_chat_generates_conversation_id_when_absent(client, agent_llm):
    agent_llm.steps.append(LLMCompletion(content="Hello.", tool_calls=[]))

    response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"]
    assert body["conversation_id"] != "conv-42"


def test_chat_empty_message_stays_422(client):
    response = client.post("/api/chat", json={"message": "  "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_chat_invalid_history_role_stays_422(client):
    response = client.post(
        "/api/chat",
        json={"message": "hi", "history": [{"role": "system", "content": "nope"}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["type"] == "literal_error"


def test_chat_maps_unavailable_llm_to_503(settings, mcp_server, retriever):
    app = create_app(
        settings,
        connector=InProcessMcpConnector(mcp_server),
        llm=ScriptedLLM([LLMUnavailableError("connection refused")]),
        retriever=retriever,
    )
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "llm_unavailable"
    assert error["error_type"] == "LLMUnavailableError"


def test_chat_maps_missing_index_to_503(settings, mcp_server, agent_llm):
    app = create_app(
        settings,
        connector=InProcessMcpConnector(mcp_server),
        llm=agent_llm,
        retriever=None,
    )
    with TestClient(app) as test_client:
        response = test_client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "rag_unavailable"
    assert "ingest" in error["message"].lower()


def test_health_still_reports_ok_with_agent_wired(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
