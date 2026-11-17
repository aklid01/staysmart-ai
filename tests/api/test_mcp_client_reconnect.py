import contextlib

import pytest

from staysmart.mcp_client import ReconnectingMcpSession, ToolFailureError


class FlakySession:
    def __init__(self) -> None:
        self.calls = 0

    async def list_tools(self) -> list[str]:
        return ["search_hotels"]

    async def call_tool(self, name, arguments):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("connection reset")
        return {"ok": True}


class SingleSessionConnector:
    def __init__(self) -> None:
        self.session = FlakySession()

    def connect(self):
        session = self.session

        @contextlib.asynccontextmanager
        async def ctx():
            yield session

        return ctx()


class ToolFailureSession:
    async def list_tools(self) -> list[str]:
        return []

    async def call_tool(self, name, arguments):
        raise ToolFailureError("hotel_error: unknown hotel", "hotel_error")


class ToolFailureConnector:
    def connect(self):
        @contextlib.asynccontextmanager
        async def ctx():
            yield ToolFailureSession()

        return ctx()


async def test_reconnecting_session_retries_once_after_transport_failure(caplog):
    session = ReconnectingMcpSession(SingleSessionConnector())

    with caplog.at_level("WARNING", logger="staysmart"):
        result = await session.call_tool("search_hotels", {})

    assert result == {"ok": True}
    assert session._session is not None
    assert any("reconnecting once" in record.message for record in caplog.records)


async def test_reconnecting_session_does_not_retry_tool_failures():
    session = ReconnectingMcpSession(ToolFailureConnector())

    with pytest.raises(ToolFailureError):
        await session.call_tool("get_hotel_details", {"hotel_id": "hotel-xxx-99"})
