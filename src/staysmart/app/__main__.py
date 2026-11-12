import uvicorn

from staysmart.app.main import create_app
from staysmart.config import Settings, configure_logging

UVICORN_LOG_LEVELS = {"critical", "error", "warning", "info", "debug", "trace"}


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    app = create_app(settings)
    log_level = settings.log_level.lower()
    if log_level not in UVICORN_LOG_LEVELS:
        log_level = "info"
    uvicorn.run(app, host=settings.http_host, port=settings.http_port, log_level=log_level)


if __name__ == "__main__":
    main()
