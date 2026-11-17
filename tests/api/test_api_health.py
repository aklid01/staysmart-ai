import contextlib

from starlette.testclient import TestClient

from staysmart.app.main import create_app

TOOL_NAMES = [
    "check_availability",
    "compare_hotels",
    "get_hotel_details",
    "get_hotel_policies",
    "search_hotels",
]


def test_health_reports_ok_with_connected_mcp_server(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "staysmart-api"
    assert body["version"] == "0.1.0"
    assert body["provider"] == "mock"
    assert body["currency"] == "USD"
    assert body["data_source"] == "mock"
    assert body["is_live"] is False
    assert body["mcp_server"]["name"] == "staysmart-hotels"
    assert body["mcp_server"]["connected"] is True
    assert body["mcp_server"]["tools"] == TOOL_NAMES


class FailingSession:
    async def list_tools(self):
        raise RuntimeError("session lost")

    async def call_tool(self, name, arguments):
        raise RuntimeError("session lost")


class FailingConnector:
    def connect(self):
        @contextlib.asynccontextmanager
        async def session():
            yield FailingSession()

        return session()


def test_health_reports_degraded_when_session_ping_fails(settings):
    app = create_app(settings, connector=FailingConnector())
    with TestClient(app) as test_client:
        response = test_client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["service"] == "staysmart-api"
    assert body["mcp_server"]["name"] == "staysmart-hotels"
    assert body["mcp_server"]["connected"] is False
    assert body["mcp_server"]["tools"] == []
    assert body["error"]["code"] == "mcp_unavailable"
    assert body["error"]["error_type"] == "McpUnavailableError"
    assert body["error"]["message"] == "RuntimeError while listing MCP tools"
