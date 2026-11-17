from staysmart.config import Settings, configure_logging
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.provider import build_provider


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    provider = build_provider(settings)
    server = build_mcp_server(settings, provider)
    server.run("stdio")


if __name__ == "__main__":
    main()
