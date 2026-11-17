import pytest

from staysmart.config import Settings
from staysmart.domain.errors import ConfigError


def test_window_days_must_be_an_integer():
    with pytest.raises(ConfigError, match="must be an integer"):
        Settings.from_env({"STAYSMART_WINDOW_DAYS": "soon"})


def test_window_days_must_be_positive():
    with pytest.raises(ConfigError, match="at least 1"):
        Settings.from_env({"STAYSMART_WINDOW_DAYS": "0"})


def test_http_port_must_be_an_integer():
    with pytest.raises(ConfigError, match="must be an integer"):
        Settings.from_env({"STAYSMART_HTTP_PORT": "8000.5"})


def test_http_port_must_be_in_range():
    with pytest.raises(ConfigError, match="between 1 and 65535"):
        Settings.from_env({"STAYSMART_HTTP_PORT": "70000"})


def test_rag_model_must_not_be_empty():
    with pytest.raises(ConfigError, match="RAG_MODEL"):
        Settings.from_env({"STAYSMART_RAG_MODEL": "   "})


def test_llm_model_must_not_be_empty():
    with pytest.raises(ConfigError, match="LLM_MODEL"):
        Settings.from_env({"LLM_MODEL": ""})


def test_llm_base_url_gets_v1_suffix():
    settings = Settings.from_env({"LLM_BASE_URL": "http://127.0.0.1:9999/"})

    assert settings.llm_base_url == "http://127.0.0.1:9999/v1"


def test_blank_cors_entries_are_dropped():
    settings = Settings.from_env({"STAYSMART_CORS_ORIGINS": "http://a.test, , http://b.test,"})

    assert settings.cors_origins == ("http://a.test", "http://b.test")
