from staysmart.config import Settings
from staysmart.mcp_server.server import build_mcp_server
from staysmart.providers.mock.provider import get_provider


def main() -> None:
    settings = Settings.from_env()
    provider = get_provider(settings)
    server = build_mcp_server(settings, provider)
    server.run("stdio")


if __name__ == "__main__":
    main()
