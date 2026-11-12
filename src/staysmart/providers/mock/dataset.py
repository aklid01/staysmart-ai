import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

from pydantic import ValidationError

from staysmart.domain.errors import ProviderError
from staysmart.domain.models import Destination, Hotel, StrictModel
from staysmart.providers.mock.inventory import InventoryContext


class DatasetFile(StrictModel):
    schema_version: int
    dataset_name: str
    currency: str
    anchor_date: date
    window_days: int
    destinations: list[Destination]
    hotels: list[Hotel]
    sold_out_overrides: dict[str, list[str]]
    blackout_dates: dict[str, list[str]]


@dataclass(frozen=True)
class MockDataset:
    schema_version: int
    dataset_name: str
    currency: str
    anchor_date: date
    window_days: int
    destinations: tuple[Destination, ...]
    hotels: tuple[Hotel, ...]
    hotels_by_id: Mapping[str, Hotel]
    destinations_by_id: Mapping[str, Destination]
    context: InventoryContext


def _validate_references(parsed: DatasetFile) -> None:
    destination_ids = {item.destination_id for item in parsed.destinations}
    if len(destination_ids) != len(parsed.destinations):
        raise ValueError("duplicate destination_id values in dataset")

    hotel_ids = {hotel.hotel_id for hotel in parsed.hotels}
    if len(hotel_ids) != len(parsed.hotels):
        raise ValueError("duplicate hotel_id values in dataset")

    room_keys: set[str] = set()
    for hotel in parsed.hotels:
        if hotel.destination_id not in destination_ids:
            raise ValueError(f"hotel {hotel.hotel_id} references unknown destination {hotel.destination_id}")
        if hotel.currency != parsed.currency:
            raise ValueError(
                f"hotel {hotel.hotel_id} currency {hotel.currency} differs from dataset currency {parsed.currency}"
            )
        for room in hotel.room_types:
            room_keys.add(f"{hotel.hotel_id}|{room.room_type_id}")

    for key, values in parsed.sold_out_overrides.items():
        if key not in room_keys:
            raise ValueError(f"sold_out_overrides references unknown room type {key}")
        for value in values:
            date.fromisoformat(value)

    for destination_id, values in parsed.blackout_dates.items():
        if destination_id not in destination_ids:
            raise ValueError(f"blackout_dates references unknown destination {destination_id}")
        for value in values:
            date.fromisoformat(value)


def load_dataset(path: Path) -> MockDataset:
    dataset_path = Path(path)
    try:
        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Cannot read mock dataset at {dataset_path}: {exc}") from exc

    try:
        parsed = DatasetFile.model_validate(raw)
        _validate_references(parsed)
    except (ValidationError, ValueError) as exc:
        raise ProviderError(f"Invalid mock dataset at {dataset_path}: {exc}") from exc

    context = InventoryContext(
        currency=parsed.currency,
        anchor_date=parsed.anchor_date,
        window_days=parsed.window_days,
        sold_out_overrides={key: frozenset(values) for key, values in parsed.sold_out_overrides.items()},
        blackout_dates={key: frozenset(values) for key, values in parsed.blackout_dates.items()},
    )
    return MockDataset(
        schema_version=parsed.schema_version,
        dataset_name=parsed.dataset_name,
        currency=parsed.currency,
        anchor_date=parsed.anchor_date,
        window_days=parsed.window_days,
        destinations=tuple(parsed.destinations),
        hotels=tuple(parsed.hotels),
        hotels_by_id={hotel.hotel_id: hotel for hotel in parsed.hotels},
        destinations_by_id={item.destination_id: item for item in parsed.destinations},
        context=context,
    )
