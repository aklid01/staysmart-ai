import json

import pytest

from staysmart.config import Settings, configure_logging
from staysmart.domain.errors import (
    ConfigError,
    CurrencyMismatchError,
    ProviderError,
)
from staysmart.providers.mock.provider import MockHotelProvider, build_provider


def test_provider_rejects_settings_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        MockHotelProvider(Settings(currency="EUR"))


def test_provider_failure_on_missing_dataset(tmp_path):
    settings = Settings(dataset_path=tmp_path / "missing.json")
    with pytest.raises(ProviderError, match="missing.json"):
        MockHotelProvider(settings)


def test_provider_failure_on_corrupt_dataset(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProviderError):
        MockHotelProvider(Settings(dataset_path=path))


def test_provider_failure_on_schema_invalid_dataset(tmp_path):
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    with pytest.raises(ProviderError):
        MockHotelProvider(Settings(dataset_path=path))


def test_settings_from_env_uses_explicit_mapping(tmp_path):
    env = {
        "HOTEL_PROVIDER": "mock",
        "STAYSMART_DATASET_PATH": str(tmp_path / "custom.json"),
        "STAYSMART_LOG_LEVEL": "DEBUG",
        "STAYSMART_CURRENCY": "USD",
        "STAYSMART_WINDOW_DAYS": "90",
    }
    settings = Settings.from_env(env=env)
    assert settings.dataset_path == tmp_path / "custom.json"
    assert settings.log_level == "DEBUG"
    assert settings.window_days == 90


def test_settings_rejects_unknown_provider():
    with pytest.raises(ConfigError):
        Settings.from_env(env={"HOTEL_PROVIDER": "live"})


def test_provider_factory(settings):
    assert isinstance(build_provider(settings), MockHotelProvider)
    with pytest.raises(ProviderError):
        build_provider(Settings(hotel_provider="live"))


def test_configure_logging_is_idempotent():
    configure_logging("WARNING")
    configure_logging("INFO")
