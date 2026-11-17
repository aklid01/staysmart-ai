from typing import Any


class StaySmartError(Exception):
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "error_type": type(self).__name__}


class InvalidDateError(StaySmartError):
    code = "invalid_date"


class UnknownDestinationError(StaySmartError):
    code = "unknown_destination"


class UnknownHotelError(StaySmartError):
    code = "unknown_hotel"


class UnknownRoomTypeError(StaySmartError):
    code = "unknown_room_type"


class CurrencyMismatchError(StaySmartError):
    code = "currency_mismatch"


class ProviderError(StaySmartError):
    code = "provider_error"


class ConfigError(StaySmartError):
    code = "config_error"


class InvalidArgumentError(StaySmartError):
    code = "invalid_argument"


ERRORS_BY_CODE: dict[str, type[StaySmartError]] = {
    error.code: error
    for error in (
        InvalidDateError,
        UnknownDestinationError,
        UnknownHotelError,
        UnknownRoomTypeError,
        CurrencyMismatchError,
        ProviderError,
        InvalidArgumentError,
    )
}
