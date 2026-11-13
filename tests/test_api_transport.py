from starlette.testclient import TestClient

from staysmart.app.main import create_app
from staysmart.app.mcp_client import StdioMcpConnector

SEARCH_BODY = {
    "destination": "Kyoto",
    "check_in": "2026-12-04",
    "check_out": "2026-12-07",
    "max_nightly_budget": 250.0,
    "min_rating": 8.0,
    "amenities": ["WIFI", "BREAKFAST"],
}


def test_stdio_transport_app_serves_health_and_search(settings):
    app = create_app(settings, connector=StdioMcpConnector(settings))
    with TestClient(app) as client:
        health = client.get("/api/health")

        assert health.status_code == 200
        assert health.json()["mcp_server"]["connected"] is True

        search = client.post("/api/search", json=SEARCH_BODY)

        assert search.status_code == 200
        assert search.json()["total_found"] == 1
        assert search.json()["results"][0]["hotel"]["hotel_id"] == "hotel-kyo-01"


def test_stdio_transport_app_maps_tool_errors(settings):
    app = create_app(settings, connector=StdioMcpConnector(settings))
    with TestClient(app) as client:
        response = client.post(
            "/api/search",
            json={"destination": "Atlantis", "check_in": "2026-12-04", "check_out": "2026-12-07"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "unknown_destination"
