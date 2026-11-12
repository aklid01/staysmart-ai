from mcp.server.mcpserver.server import MCPServer

from staysmart.config import Settings, configure_logging
from staysmart.mcp_server.tools import register_tools
from staysmart.providers.base import HotelProvider

SERVER_NAME = "staysmart-hotels"
SERVER_VERSION = "0.1.0"
INSTRUCTIONS = (
    "Hotel discovery tools over a local mock dataset. Every result carries "
    "data_source='mock' and is_live=False. Prices and availability come only "
    "from these tools; policy documents are descriptive, never live data. "
    "Dates are ISO strings and currency is pinned by the server."
)

SDK_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def build_mcp_server(settings: Settings, provider: HotelProvider) -> MCPServer:
    configure_logging(settings.log_level)
    sdk_log_level = settings.log_level if settings.log_level in SDK_LOG_LEVELS else "INFO"
    server = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions=INSTRUCTIONS,
        log_level=sdk_log_level,
    )
    register_tools(server, settings, provider)
    return server
