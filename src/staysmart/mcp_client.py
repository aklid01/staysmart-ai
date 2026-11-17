import asyncio
import contextlib
import logging
import re
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, TypeVar

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.server import MCPServer

from staysmart.config import PROJECT_ROOT, Settings
from staysmart.domain.errors import ERRORS_BY_CODE

logger = logging.getLogger("staysmart")

_CODE_PREFIX = re.compile(r"^([a-z][a-z0-9_]*):\s")
T = TypeVar("T")


class ToolFailureError(Exception):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class McpSession(Protocol):
    async def list_tools(self) -> list[str]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None: ...


class McpConnector(Protocol):
    def connect(self) -> AbstractAsyncContextManager[McpSession]: ...


class ReconnectingMcpSession:
    def __init__(self, connector: McpConnector) -> None:
        self._connector = connector
        self._context: AbstractAsyncContextManager[McpSession] | None = None
        self._session: McpSession | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        async with self._lock:
            if self._session is None:
                await self._connect()

    async def close(self) -> None:
        async with self._lock:
            context, self._context, self._session = self._context, None, None
            if context is not None:
                await context.__aexit__(None, None, None)

    async def list_tools(self) -> list[str]:
        return await self._dispatch(lambda session: session.list_tools())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._dispatch(lambda session: session.call_tool(name, arguments))

    async def _connect(self) -> None:
        context = self._connector.connect()
        self._session = await context.__aenter__()
        self._context = context

    async def _acquire(self) -> McpSession:
        async with self._lock:
            if self._session is None:
                await self._connect()
            if self._session is None:
                raise RuntimeError("MCP session failed to connect")
            return self._session

    async def _dispatch(self, operation: Callable[[McpSession], Any]) -> Any:
        session = await self._acquire()
        try:
            return await operation(session)
        except ToolFailureError:
            raise
        except Exception as exc:
            logger.warning("MCP session call failed (%s: %s); reconnecting once", type(exc).__name__, exc)
            await self.close()
            session = await self._acquire()
            return await operation(session)


class SdkMcpSession:
    def __init__(self, client: Client) -> None:
        self._client = client

    async def list_tools(self) -> list[str]:
        listing = await self._client.list_tools()
        return sorted(tool.name for tool in listing.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        result = await self._client.call_tool(name, arguments)
        if result.is_error:
            raise _parse_tool_failure(result.content[0].text)
        return result.structured_content


def _parse_tool_failure(text: str) -> ToolFailureError:
    stripped = _strip_sdk_prefix(text)
    match = _CODE_PREFIX.match(stripped)
    if match and match.group(1) in ERRORS_BY_CODE:
        return ToolFailureError(stripped[match.end() :].strip(), match.group(1))
    return ToolFailureError(stripped)


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
                "STAYSMART_DATASET_PATH": str(self._settings.dataset_path),
                "STAYSMART_CURRENCY": self._settings.currency,
                "STAYSMART_WINDOW_DAYS": str(self._settings.window_days),
                "HOTEL_PROVIDER": self._settings.hotel_provider,
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
