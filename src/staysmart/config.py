import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from staysmart.domain.errors import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = PROJECT_ROOT / "data" / "hotels" / "v1" / "hotels.json"
DEFAULT_RAG_CORPUS_PATH = PROJECT_ROOT / "data" / "knowledge" / "v1"
DEFAULT_RAG_INDEX_PATH = PROJECT_ROOT / "data" / "rag" / "index"
DEFAULT_RAG_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_LLM_BASE_URL = "http://127.0.0.1:3425/v1"
DEFAULT_LLM_MODEL = "auto/glm-5.3-flash"
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
MIN_HTTP_PORT = 1
MAX_HTTP_PORT = 65535


@dataclass(frozen=True)
class Settings:
    hotel_provider: str = "mock"
    dataset_path: Path = DEFAULT_DATASET_PATH
    log_level: str = "INFO"
    currency: str = "USD"
    window_days: int = 365
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    rag_corpus_path: Path = DEFAULT_RAG_CORPUS_PATH
    rag_index_path: Path = DEFAULT_RAG_INDEX_PATH
    rag_model: str = DEFAULT_RAG_MODEL
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: str = ""
    llm_model: str = DEFAULT_LLM_MODEL

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        if env is None:
            load_dotenv()
            source: Mapping[str, str] = os.environ
        else:
            source = env

        return cls(
            hotel_provider=_resolve_provider(source),
            dataset_path=_resolve_path(source, "STAYSMART_DATASET_PATH", DEFAULT_DATASET_PATH),
            log_level=source.get("STAYSMART_LOG_LEVEL", "INFO").upper(),
            currency=source.get("STAYSMART_CURRENCY", "USD").upper(),
            window_days=_resolve_window_days(source),
            http_host=source.get("STAYSMART_HTTP_HOST", "127.0.0.1"),
            http_port=_resolve_http_port(source),
            cors_origins=_resolve_cors_origins(source),
            rag_corpus_path=_resolve_path(source, "STAYSMART_RAG_CORPUS_PATH", DEFAULT_RAG_CORPUS_PATH),
            rag_index_path=_resolve_path(source, "STAYSMART_RAG_INDEX_PATH", DEFAULT_RAG_INDEX_PATH),
            rag_model=_resolve_rag_model(source),
            llm_base_url=_resolve_llm_base_url(source),
            llm_api_key=source.get("LLM_API_KEY", ""),
            llm_model=_resolve_llm_model(source),
        )


def _resolve_provider(source: Mapping[str, str]) -> str:
    provider = source.get("HOTEL_PROVIDER", "mock")
    if provider != "mock":
        raise ConfigError(f"Unsupported HOTEL_PROVIDER={provider!r}; only 'mock' is available")
    return provider


def _resolve_path(source: Mapping[str, str], key: str, default: Path) -> Path:
    raw = source.get(key, "")
    return Path(raw) if raw else default


def _resolve_window_days(source: Mapping[str, str]) -> int:
    raw = source.get("STAYSMART_WINDOW_DAYS", "365")
    try:
        window_days = int(raw)
    except ValueError as exc:
        raise ConfigError(f"STAYSMART_WINDOW_DAYS must be an integer, got {raw!r}") from exc
    if window_days < 1:
        raise ConfigError("STAYSMART_WINDOW_DAYS must be at least 1")
    return window_days


def _resolve_http_port(source: Mapping[str, str]) -> int:
    raw = source.get("STAYSMART_HTTP_PORT", "8000")
    try:
        http_port = int(raw)
    except ValueError as exc:
        raise ConfigError(f"STAYSMART_HTTP_PORT must be an integer, got {raw!r}") from exc
    if not MIN_HTTP_PORT <= http_port <= MAX_HTTP_PORT:
        raise ConfigError(f"STAYSMART_HTTP_PORT must be between {MIN_HTTP_PORT} and {MAX_HTTP_PORT}, got {http_port}")
    return http_port


def _resolve_cors_origins(source: Mapping[str, str]) -> tuple[str, ...]:
    raw = source.get("STAYSMART_CORS_ORIGINS")
    if raw is None:
        return DEFAULT_CORS_ORIGINS
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


def _resolve_rag_model(source: Mapping[str, str]) -> str:
    rag_model = source.get("STAYSMART_RAG_MODEL", DEFAULT_RAG_MODEL).strip()
    if not rag_model:
        raise ConfigError("STAYSMART_RAG_MODEL must not be empty")
    return rag_model


def _resolve_llm_base_url(source: Mapping[str, str]) -> str:
    base_url = source.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip().rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return base_url


def _resolve_llm_model(source: Mapping[str, str]) -> str:
    llm_model = source.get("LLM_MODEL", DEFAULT_LLM_MODEL).strip()
    if not llm_model:
        raise ConfigError("LLM_MODEL must not be empty")
    return llm_model


def configure_logging(level: str) -> None:
    logger = logging.getLogger("staysmart")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
