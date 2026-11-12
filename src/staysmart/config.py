import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from staysmart.domain.errors import ProviderError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "hotels" / "v1" / "hotels.json"
DEFAULT_RAG_CORPUS_PATH = PROJECT_ROOT / "data" / "knowledge" / "v1"
DEFAULT_RAG_INDEX_PATH = PROJECT_ROOT / "data" / "rag" / "index"
DEFAULT_RAG_MODEL = "BAAI/bge-small-en-v1.5"


@dataclass(frozen=True)
class Settings:
    hotel_provider: str = "mock"
    dataset_path: Path = DEFAULT_DATASET_PATH
    log_level: str = "INFO"
    currency: str = "USD"
    window_days: int = 365
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    rag_corpus_path: Path = DEFAULT_RAG_CORPUS_PATH
    rag_index_path: Path = DEFAULT_RAG_INDEX_PATH
    rag_model: str = DEFAULT_RAG_MODEL

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

        http_host = source.get("STAYSMART_HTTP_HOST", "127.0.0.1")

        raw_port = source.get("STAYSMART_HTTP_PORT", "8000")
        try:
            http_port = int(raw_port)
        except ValueError as exc:
            raise ProviderError(f"STAYSMART_HTTP_PORT must be an integer, got {raw_port!r}") from exc
        if not 1 <= http_port <= 65535:
            raise ProviderError(f"STAYSMART_HTTP_PORT must be between 1 and 65535, got {http_port}")

        cors_origins = tuple(
            origin.strip()
            for origin in source.get(
                "STAYSMART_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        )

        rag_corpus_raw = source.get("STAYSMART_RAG_CORPUS_PATH", "")
        rag_corpus_path = Path(rag_corpus_raw) if rag_corpus_raw else DEFAULT_RAG_CORPUS_PATH
        rag_index_raw = source.get("STAYSMART_RAG_INDEX_PATH", "")
        rag_index_path = Path(rag_index_raw) if rag_index_raw else DEFAULT_RAG_INDEX_PATH
        rag_model = source.get("STAYSMART_RAG_MODEL", DEFAULT_RAG_MODEL).strip()
        if not rag_model:
            raise ProviderError("STAYSMART_RAG_MODEL must not be empty")

        return cls(
            hotel_provider=provider,
            dataset_path=dataset_path,
            log_level=log_level,
            currency=currency,
            window_days=window_days,
            http_host=http_host,
            http_port=http_port,
            cors_origins=cors_origins,
            rag_corpus_path=rag_corpus_path,
            rag_index_path=rag_index_path,
            rag_model=rag_model,
        )


def configure_logging(level: str) -> None:
    logger = logging.getLogger("staysmart")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
