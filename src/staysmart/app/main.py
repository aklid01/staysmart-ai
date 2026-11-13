import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from staysmart.agent.llm import ChatLLM, OpenAICompatLLM
from staysmart.app.errors import install_error_handlers
from staysmart.app.mcp_client import McpConnector, ReconnectingMcpSession, StdioMcpConnector
from staysmart.app.routes import register_routes
from staysmart.config import Settings
from staysmart.rag.service import RagRetriever

APP_NAME = "staysmart-api"

try:
    APP_VERSION = version("staysmart-ai")
except PackageNotFoundError:
    APP_VERSION = "0.0.0"


def create_app(
    settings: Settings,
    connector: McpConnector | None = None,
    llm: ChatLLM | None = None,
    retriever: RagRetriever | None = None,
) -> Starlette:
    connector = connector or StdioMcpConnector(settings)
    llm = llm or OpenAICompatLLM(settings)
    logger = logging.getLogger("staysmart")

    @asynccontextmanager
    async def lifespan(app: Starlette):
        session = ReconnectingMcpSession(connector)
        await session.open()
        app.state.mcp = session
        logger.info("MCP session established")
        try:
            yield
        finally:
            await session.close()
            logger.info("MCP session closed")

    app = Starlette(lifespan=lifespan)
    app.state.settings = settings
    app.state.connector = connector
    app.state.llm = llm
    app.state.retriever = retriever
    app.state.app_name = APP_NAME
    app.state.app_version = APP_VERSION
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    register_routes(app)
    return app
