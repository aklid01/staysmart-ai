from starlette.routing import Route
from starlette.testclient import TestClient


def test_unhandled_exception_maps_to_internal_error_json(app):
    async def boom(request) -> None:
        raise RuntimeError("exploded")

    app.routes.append(Route("/api/boom", boom, methods=["GET"]))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/boom")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert error["error_type"] == "UnhandledError"
    assert error["message"] == "Internal server error"
