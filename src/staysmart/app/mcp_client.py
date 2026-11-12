import contextlib
import sys
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.server import MCPServer

from staysmart.config import PROJECT_ROOT, Settings


class ToolFailureError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class McpSession(Protocol):
    async def list_tools(self) -> list[str]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class McpConnector(Protocol):
    def connect(self) -> AbstractAsyncContextManager[McpSession]: ...


class SdkMcpSession:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_tools(self) -> list[str]:
        listing = await self._client.list_tools()
        return sorted(tool.name for tool in listing.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._client.call_tool(name, arguments)
        if result.is_error:
            raise ToolFailureError(_strip_sdk_prefix(result.content[0].text))
        return result.structured_content


def _strip_sdk_prefix(text: str) -> str:
    if not text.startswith("Error executing tool"):
        return text
    head, separator, tail = text.partition(": ")
    if separator and tail:
        return tail
    return text


def _client_session(client: Client) -> AbstractAsyncContextManager[McpSession]:
    @contextlib.asynccontextmanager
    async def session() -> AsyncIterator[McpSession]:
        async with client as connected:
            yield SdkMcpSession(connected)

    return session()


class StdioMcpConnector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def connect(self) -> AbstractAsyncContextManager[McpSession]:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "staysmart.mcp_server"],
            cwd=str(PROJECT_ROOT),
            env={
                "STAYSMART_LOG_LEVEL": self._settings.log_level,
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            },
        )
        return _client_session(Client(server=params))


class InProcessMcpConnector:
    def __init__(self, server: MCPServer) -> None:
        self._server = server

    def connect(self) -> AbstractAsyncContextManager[McpSession]:
        return _client_session(Client(server=self._server))
