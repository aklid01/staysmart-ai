import contextlib

from bodies import KYOTO_SEARCH_BODY
from starlette.testclient import TestClient

from staysmart.app.main import create_app
from staysmart.mcp_client import InProcessMcpConnector
from staysmart.mcp_server.server import build_mcp_server


class ExplodingProvider:
    async def search(self, query):
        raise RuntimeError("boom")

    async def get_hotel_details(self, hotel_id, **kwargs):
        raise RuntimeError("boom")

    async def check_availability(self, hotel_id, room_type_id, check_in, check_out, rooms=1):
        raise RuntimeError("boom")


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


def test_exploding_provider_maps_to_generic_tool_error(settings):
    exploding = ExplodingProvider()
    app = create_app(settings, connector=InProcessMcpConnector(build_mcp_server(settings, exploding)))
    with TestClient(app) as client:
        response = client.post("/api/search", json=KYOTO_SEARCH_BODY)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "tool_error"
    assert error["error_type"] == "ToolError"
    assert error["message"] == "Error executing tool search_hotels"


def test_session_failure_maps_to_unavailable(settings):
    app = create_app(settings, connector=FailingConnector())
    with TestClient(app) as client:
        response = client.post("/api/search", json=KYOTO_SEARCH_BODY)

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "mcp_unavailable"
    assert error["error_type"] == "McpUnavailableError"
    assert error["message"] == "RuntimeError while calling tool search_hotels"


def test_cors_preflight_allows_configured_origin(client):
    response = client.options(
        "/api/search",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_rejects_unknown_origin(client):
    response = client.options(
        "/api/search",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers
