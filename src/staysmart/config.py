import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from staysmart.domain.errors import ProviderError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "hotels" / "v1" / "hotels.json"


@dataclass(frozen=True)
class Settings:
    hotel_provider: str = "mock"
    dataset_path: Path = DEFAULT_DATASET_PATH
    log_level: str = "INFO"
    currency: str = "USD"
    window_days: int = 365

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        if env is None:
            load_dotenv()
            source: Mapping[str, str] = os.environ
        else:
            source = env

        provider = source.get("HOTEL_PROVIDER", "mock")
        if provider != "mock":
            raise ProviderError(f"Unsupported HOTEL_PROVIDER={provider!r}; only 'mock' is available")

        raw_path = source.get("STAYSMART_DATASET_PATH", "")
        dataset_path = Path(raw_path) if raw_path else DEFAULT_DATASET_PATH
        log_level = source.get("STAYSMART_LOG_LEVEL", "INFO").upper()
        currency = source.get("STAYSMART_CURRENCY", "USD").upper()

        raw_window = source.get("STAYSMART_WINDOW_DAYS", "365")
        try:
            window_days = int(raw_window)
        except ValueError as exc:
            raise ProviderError(f"STAYSMART_WINDOW_DAYS must be an integer, got {raw_window!r}") from exc
        if window_days < 1:
            raise ProviderError("STAYSMART_WINDOW_DAYS must be at least 1")

        return cls(
            hotel_provider=provider,
            dataset_path=dataset_path,
            log_level=log_level,
            currency=currency,
            window_days=window_days,
        )


def configure_logging(level: str) -> None:
    logger = logging.getLogger("staysmart")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
