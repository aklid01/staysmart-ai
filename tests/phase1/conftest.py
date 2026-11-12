from datetime import date
from pathlib import Path

import pytest

from staysmart.config import Settings
from staysmart.providers.mock.dataset import load_dataset
from staysmart.providers.mock.provider import MockHotelProvider

ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "hotels" / "v1" / "hotels.json"
GOLDEN_PATH = ROOT / "tests" / "phase1" / "golden" / "provider_demo.json"
ARTIFACT_PATH = ROOT / "artifacts" / "provider_demo.json"
DEMO_SCRIPT = ROOT / "scripts" / "demo_provider.py"
CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)


@pytest.fixture
def settings():
    return Settings(
        hotel_provider="mock",
        dataset_path=DATASET_PATH,
        log_level="WARNING",
        currency="USD",
        window_days=365,
    )


@pytest.fixture
def provider(settings):
    return MockHotelProvider(settings)


@pytest.fixture
def dataset():
    return load_dataset(DATASET_PATH)


@pytest.fixture
def golden_path():
    return GOLDEN_PATH


@pytest.fixture
def artifact_path():
    return ARTIFACT_PATH


@pytest.fixture
def demo_script():
    return DEMO_SCRIPT
