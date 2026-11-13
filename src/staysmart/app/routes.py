import json
import logging
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from staysmart.agent.agent import HotelAgent
from staysmart.app.errors import ApiError, classify_tool_failure, invalid_json_error, unavailable_error
from staysmart.app.mcp_client import ToolFailureError
from staysmart.config import Settings
from staysmart.domain.models import Amenity
from staysmart.mcp_server.server import SERVER_NAME
from staysmart.rag.embedder import FastEmbedEmbedder
from staysmart.rag.errors import RagError
from staysmart.rag.service import RagRetriever

logger = logging.getLogger("staysmart")


class _RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchRequest(_RequestModel):
    destination: str = Field(min_length=1)
    check_in: date
    check_out: date
    guests: int = Field(default=2, ge=1)
    rooms: int = Field(default=1, ge=1)
    max_nightly_budget: float | None = None
    min_rating: float | None = None
    amenities: list[Amenity] = []
    preferences: list[str] = []


class DetailsQuery(_RequestModel):
    check_in: date | None = None
    check_out: date | None = None
    rooms: int = Field(default=1, ge=1)
    guests: int = Field(default=2, ge=1)


class AvailabilityRequest(_RequestModel):
    room_type_id: str = Field(min_length=1)
    check_in: date
    check_out: date
    rooms: int = Field(default=1, ge=1)


class CompareRequest(_RequestModel):
    hotel_ids: list[str]
    check_in: date
    check_out: date
    rooms: int = Field(default=1, ge=1)
    guests: int = Field(default=2, ge=1)
    preferences: list[str] = []


class ChatMessage(_RequestModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(_RequestModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    history: list[ChatMessage] = []

    @model_validator(mode="after")
    def validate_message(self) -> "ChatRequest":
        if not self.message.strip():
            raise ValueError("message must not be blank")
        return self


async def _json_model(request: Request, model_cls: type[BaseModel]) -> BaseModel:
    raw = await request.body()
    if not raw.strip():
        raise invalid_json_error()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise invalid_json_error() from exc
    return model_cls.model_validate(data)


async def _call_tool(session: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await session.call_tool(name, arguments)
    except ToolFailureError as exc:
        raise classify_tool_failure(exc.message, exc.code) from exc
    except Exception as exc:
        logger.warning("MCP tool call %s failed at transport level: %s", name, exc)
        raise unavailable_error(f"{type(exc).__name__} while calling tool {name}") from exc
    if not isinstance(result, dict):
        raise ApiError(502, "tool_error", f"tool {name} returned no structured payload", "ToolError")
    return result


async def health(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    base = {
        "service": request.app.state.app_name,
        "version": request.app.state.app_version,
        "provider": settings.hotel_provider,
        "currency": settings.currency,
        "data_source": "mock",
        "is_live": False,
    }
    try:
        tools = await request.app.state.mcp.list_tools()
    except Exception as exc:
        logger.warning("Health check degraded: %s", exc)
        body = {
            **base,
            "status": "degraded",
            "mcp_server": {"name": SERVER_NAME, "connected": False, "tools": []},
            "error": {
                "code": "mcp_unavailable",
                "message": f"{type(exc).__name__} while listing MCP tools",
                "error_type": "McpUnavailableError",
            },
        }
        return JSONResponse(body, status_code=503)
    body = {
        **base,
        "status": "ok",
        "mcp_server": {"name": SERVER_NAME, "connected": True, "tools": tools},
    }
    return JSONResponse(body)


async def search_hotels(request: Request) -> JSONResponse:
    payload = await _json_model(request, SearchRequest)
    result = await _call_tool(request.app.state.mcp, "search_hotels", payload.model_dump(mode="json"))
    return JSONResponse(result)


async def hotel_details(request: Request) -> JSONResponse:
    query = DetailsQuery.model_validate(dict(request.query_params))
    arguments = {"hotel_id": request.path_params["hotel_id"], **query.model_dump(mode="json")}
    result = await _call_tool(request.app.state.mcp, "get_hotel_details", arguments)
    return JSONResponse(result)


async def hotel_policies(request: Request) -> JSONResponse:
    result = await _call_tool(
        request.app.state.mcp, "get_hotel_policies", {"hotel_id": request.path_params["hotel_id"]}
    )
    return JSONResponse(result)


async def check_availability(request: Request) -> JSONResponse:
    payload = await _json_model(request, AvailabilityRequest)
    arguments = {"hotel_id": request.path_params["hotel_id"], **payload.model_dump(mode="json")}
    result = await _call_tool(request.app.state.mcp, "check_availability", arguments)
    return JSONResponse(result)


async def compare_hotels(request: Request) -> JSONResponse:
    payload = await _json_model(request, CompareRequest)
    result = await _call_tool(request.app.state.mcp, "compare_hotels", payload.model_dump(mode="json"))
    return JSONResponse(result)


async def chat(request: Request) -> JSONResponse:
    payload = await _json_model(request, ChatRequest)
    agent = _get_agent(request)
    result = await agent.run(
        payload.message,
        history=[entry.model_dump() for entry in payload.history],
        session=request.app.state.mcp,
        conversation_id=payload.conversation_id,
    )
    return JSONResponse(result.model_dump(mode="json"))


def _get_agent(request: Request) -> HotelAgent:
    app = request.app
    agent = getattr(app.state, "agent", None)
    if agent is not None:
        return agent
    if app.state.retriever is None:
        try:
            app.state.retriever = RagRetriever.load(
                app.state.settings.rag_index_path,
                FastEmbedEmbedder(app.state.settings.rag_model),
                corpus_path=app.state.settings.rag_corpus_path,
            )
        except RagError as exc:
            raise ApiError(
                503,
                "rag_unavailable",
                f"{exc.message} Run 'python -m staysmart.rag ingest' first.",
                "RagUnavailableError",
            ) from exc
    app.state.agent = HotelAgent(app.state.llm, app.state.retriever)
    return app.state.agent


def register_routes(app: Starlette) -> None:
    app.routes.append(Route("/api/health", health, methods=["GET"]))
    app.routes.append(Route("/api/search", search_hotels, methods=["POST"]))
    app.routes.append(Route("/api/hotels/{hotel_id}", hotel_details, methods=["GET"]))
    app.routes.append(Route("/api/hotels/{hotel_id}/policies", hotel_policies, methods=["GET"]))
    app.routes.append(Route("/api/hotels/{hotel_id}/availability", check_availability, methods=["POST"]))
    app.routes.append(Route("/api/compare", compare_hotels, methods=["POST"]))
    app.routes.append(Route("/api/chat", chat, methods=["POST"]))
