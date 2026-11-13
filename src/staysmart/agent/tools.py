import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from staysmart.app.mcp_client import ToolFailureError
from staysmart.rag.models import Category
from staysmart.rag.service import RagRetriever

HOTEL_TOOLS = frozenset(
    {"search_hotels", "get_hotel_details", "check_availability", "compare_hotels", "get_hotel_policies"}
)

KNOWLEDGE_TOOL = "search_knowledge"
AGENT_TOOL_NAMES = HOTEL_TOOLS | {KNOWLEDGE_TOOL}

AMENITY_VALUES = [
    "WIFI",
    "POOL",
    "GYM",
    "BREAKFAST",
    "PARKING",
    "SPA",
    "PET_FRIENDLY",
    "AIR_CONDITIONING",
    "RESTAURANT",
    "SHUTTLE",
]

KNOWLEDGE_CATEGORIES = [category.value for category in Category]


class ToolStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class ToolOutcome:
    status: ToolStatus
    payload: Any

    @classmethod
    def ok(cls, payload: dict[str, Any]) -> "ToolOutcome":
        if not isinstance(payload, dict):
            raise TypeError("ok outcomes require a dict payload")
        return cls(ToolStatus.OK, payload)

    @classmethod
    def error(cls, message: str) -> "ToolOutcome":
        if not isinstance(message, str):
            raise TypeError("error outcomes require a string message")
        return cls(ToolStatus.ERROR, message)


AGENT_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": (
                "Search hotels in a destination for a stay. Filters by nightly budget, minimum "
                "guest rating and required amenities. Returns one best quote per hotel with "
                "availability flags, sold-out dates and unmet preferences."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string", "description": "City or region, e.g. Kyoto"},
                    "check_in": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "check_out": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "guests": {"type": "integer", "default": 2},
                    "rooms": {"type": "integer", "default": 1},
                    "max_nightly_budget": {"type": "number", "nullable": True},
                    "min_rating": {"type": "number", "nullable": True},
                    "amenities": {"type": "array", "items": {"type": "string", "enum": AMENITY_VALUES}},
                    "preferences": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["destination", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hotel_details",
            "description": (
                "Full details for one hotel: description, amenities, room types with quotes for "
                "the stay dates, and the cancellation policy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hotel_id": {"type": "string"},
                    "check_in": {"type": "string", "nullable": True, "description": "ISO date"},
                    "check_out": {"type": "string", "nullable": True, "description": "ISO date"},
                    "rooms": {"type": "integer", "default": 1},
                    "guests": {"type": "integer", "default": 2},
                },
                "required": ["hotel_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Per-night availability and pricing for one room type over a date range. Sold-out "
                "or partial stays are normal results carrying sold-out dates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hotel_id": {"type": "string"},
                    "room_type_id": {"type": "string"},
                    "check_in": {"type": "string", "description": "ISO date"},
                    "check_out": {"type": "string", "description": "ISO date"},
                    "rooms": {"type": "integer", "default": 1},
                },
                "required": ["hotel_id", "room_type_id", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_hotels",
            "description": (
                "Compare several hotels side by side for the same stay: prices, rating, location, "
                "amenities, cancellation policy and availability. Unknown ids are reported in "
                "unresolved_hotel_ids instead of failing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hotel_ids": {"type": "array", "items": {"type": "string"}},
                    "check_in": {"type": "string", "description": "ISO date"},
                    "check_out": {"type": "string", "description": "ISO date"},
                    "rooms": {"type": "integer", "default": 1},
                    "guests": {"type": "integer", "default": 2},
                    "preferences": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["hotel_ids", "check_in", "check_out"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hotel_policies",
            "description": (
                "Grounded policy facts for one hotel: cancellation terms, pet policy and explicit information gaps."
            ),
            "parameters": {
                "type": "object",
                "properties": {"hotel_id": {"type": "string"}},
                "required": ["hotel_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Retrieve hotel knowledge documents: pet rules, check-in/check-out requirements, "
                "room and amenity descriptions, cancellation wording and destination guidance. "
                "Returns grounded text chunks with sources. Never contains prices or availability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "hotel_id": {"type": "string", "nullable": True},
                    "destination_id": {"type": "string", "nullable": True},
                    "category": {"type": "string", "nullable": True, "enum": KNOWLEDGE_CATEGORIES},
                },
                "required": ["query"],
            },
        },
    },
]


async def execute_agent_tool(
    name: str,
    arguments: dict[str, Any],
    session: Any,
    retriever: RagRetriever,
) -> ToolOutcome:
    if not isinstance(arguments, dict):
        return ToolOutcome.error("Error: tool arguments must be an object.")
    if name not in AGENT_TOOL_NAMES:
        return ToolOutcome.error(f"Error: unknown tool {name!r}.")
    if name == KNOWLEDGE_TOOL:
        return await _run_knowledge(arguments, retriever)
    return await _run_hotel_tool(name, arguments, session)


async def _run_knowledge(arguments: dict[str, Any], retriever: RagRetriever) -> ToolOutcome:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return ToolOutcome.error("Error: search_knowledge requires a non-empty query.")
    bundle = retriever.build_context(
        query,
        hotel_id=arguments.get("hotel_id") or None,
        destination_id=arguments.get("destination_id") or None,
        category=arguments.get("category") or None,
    )
    payload = {
        "formatted_context": bundle.formatted_context,
        "sources": [source.model_dump() for source in bundle.sources],
    }
    return ToolOutcome.ok(payload)


async def _run_hotel_tool(name: str, arguments: dict[str, Any], session: Any) -> ToolOutcome:
    try:
        payload = await session.call_tool(name, arguments)
    except ToolFailureError as exc:
        return ToolOutcome.error(f"Error: {exc.message}")
    except Exception as exc:  # noqa: BLE001 - transport failures become tool feedback
        return ToolOutcome.error(f"Error: MCP session unavailable ({type(exc).__name__}).")
    if not isinstance(payload, dict):
        return ToolOutcome.error("Error: tool returned no structured payload.")
    return ToolOutcome.ok(payload)


def canonical_arguments(arguments: dict[str, Any]) -> str:
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False)
