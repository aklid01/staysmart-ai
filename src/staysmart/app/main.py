import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from staysmart.app.errors import install_error_handlers
from staysmart.app.mcp_client import McpConnector, StdioMcpConnector
from staysmart.app.routes import register_routes
from staysmart.config import Settings

APP_NAME = "staysmart-api"

try:
    APP_VERSION = version("staysmart-ai")
except PackageNotFoundError:
    APP_VERSION = "0.0.0"


def create_app(settings: Settings, connector: McpConnector | None = None) -> Starlette:
    connector = connector or StdioMcpConnector(settings)
    logger = logging.getLogger("staysmart")

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with connector.connect() as session:
            app.state.mcp = session
            logger.info("MCP session established")
            yield
        logger.info("MCP session closed")

    app = Starlette(lifespan=lifespan)
    app.state.settings = settings
    app.state.connector = connector
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
