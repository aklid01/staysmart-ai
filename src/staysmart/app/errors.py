import json
import logging
from typing import Any

from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse

from staysmart.agent.errors import LLMUnavailableError
from staysmart.domain.errors import StaySmartError
from staysmart.rag.errors import RagError

logger = logging.getLogger("staysmart")


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        error_type: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.error_type = error_type
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "error_type": self.error_type,
        }
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


_TOOL_FAILURE_MAP: tuple[tuple[str, int, str, str], ...] = (
    ("No destination matches", 404, "unknown_destination", "UnknownDestinationError"),
    ("Unknown hotel_id", 404, "unknown_hotel", "UnknownHotelError"),
    ("Unknown room_type_id", 404, "unknown_room_type", "UnknownRoomTypeError"),
    ("hotel_ids must contain at least one hotel id", 400, "empty_hotel_ids", "ToolError"),
    ("check_out must be after check_in", 400, "invalid_date", "InvalidDateError"),
    ("Stay must be between 1 and", 400, "invalid_date", "InvalidDateError"),
    ("stay length must be between 1 and", 400, "invalid_date", "InvalidDateError"),
    ("outside the mock dataset window", 400, "invalid_date", "InvalidDateError"),
)

_TOOL_CODE_MAP: dict[str, tuple[int, str]] = {
    "unknown_destination": (404, "UnknownDestinationError"),
    "unknown_hotel": (404, "UnknownHotelError"),
    "unknown_room_type": (404, "UnknownRoomTypeError"),
    "invalid_date": (400, "InvalidDateError"),
    "currency_mismatch": (502, "CurrencyMismatchError"),
    "provider_error": (502, "ProviderError"),
}


def classify_tool_failure(message: str, code: str | None = None) -> ApiError:
    if code is not None and code in _TOOL_CODE_MAP:
        status_code, error_type = _TOOL_CODE_MAP[code]
        return ApiError(status_code, code, message, error_type)
    for fragment, status_code, code, error_type in _TOOL_FAILURE_MAP:
        if fragment in message:
            return ApiError(status_code, code, message, error_type)
    return ApiError(502, "tool_error", message, "ToolError")


def unavailable_error(message: str) -> ApiError:
    return ApiError(503, "mcp_unavailable", message, "McpUnavailableError")


def invalid_json_error() -> ApiError:
    return ApiError(400, "invalid_json", "Request body is not valid JSON", "InvalidJsonError")


def _validation_details(exc: ValidationError) -> list[dict[str, Any]]:
    return [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]


def install_error_handlers(app: Starlette) -> None:
    app.add_exception_handler(ApiError, _handle_api_error)
    app.add_exception_handler(json.JSONDecodeError, _handle_invalid_json)
    app.add_exception_handler(ValidationError, _handle_validation_error)
    app.add_exception_handler(StaySmartError, _handle_stay_smart_error)
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)


async def _handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(exc.to_dict(), status_code=exc.status_code)


async def _handle_stay_smart_error(request: Request, exc: StaySmartError) -> JSONResponse:
    if isinstance(exc, LLMUnavailableError):
        status_code, code = 503, "llm_unavailable"
    elif isinstance(exc, RagError):
        status_code, code = 503, "rag_unavailable"
    else:
        status_code, code = 500, exc.code
    body = {"error": {"code": code, "message": exc.message, "error_type": type(exc).__name__}}
    return JSONResponse(body, status_code=status_code)


async def _handle_invalid_json(request: Request, exc: json.JSONDecodeError) -> JSONResponse:
    return JSONResponse(invalid_json_error().to_dict(), status_code=400)


async def _handle_validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    error = ApiError(
        422,
        "validation_error",
        "Request validation failed",
        "ValidationError",
        details=_validation_details(exc),
    )
    return JSONResponse(error.to_dict(), status_code=422)


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    if exc.status_code == 404:
        error = ApiError(
            404,
            "not_found",
            f"Route not found: {request.method} {request.url.path}",
            "NotFoundError",
        )
    elif exc.status_code == 405:
        error = ApiError(
            405,
            "method_not_allowed",
            f"Method not allowed: {request.method} {request.url.path}",
            "MethodNotAllowedError",
        )
    else:
        error = ApiError(exc.status_code, f"http_{exc.status_code}", str(exc.detail), "HTTPError")
    return JSONResponse(error.to_dict(), status_code=exc.status_code)


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error")
    error = ApiError(500, "internal_error", "Internal server error", "UnhandledError")
    return JSONResponse(error.to_dict(), status_code=500)
