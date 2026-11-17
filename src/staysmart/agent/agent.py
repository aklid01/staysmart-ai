import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import Field

from staysmart.agent.errors import AgentError
from staysmart.agent.llm import ChatLLM, LLMCompletion
from staysmart.agent.prompts import SYSTEM_PROMPT
from staysmart.agent.tools import (
    AGENT_TOOLS,
    KNOWLEDGE_TOOL,
    ToolStatus,
    canonical_arguments,
    execute_agent_tool,
)
from staysmart.domain.base import StrictModel
from staysmart.mcp_client import McpSession
from staysmart.rag.models import ContextSource
from staysmart.rag.service import RagRetriever

logger = logging.getLogger("staysmart")

MAX_TURNS = 6
MAX_TOOL_CALLS = 12


class TurnOutcome(str, Enum):
    ANSWERED = "answered"
    BUDGET_EXHAUSTED = "budget_exhausted"
    TURNS_EXHAUSTED = "turns_exhausted"


class TraceEntry(StrictModel):
    tool: str
    status: ToolStatus


class AgentTurnResult(StrictModel):
    message: str
    hotels: list[dict[str, Any]]
    tool_trace: list[TraceEntry]
    conversation_id: str
    sources: list[ContextSource] = Field(default_factory=list)
    comparison: dict[str, Any] | None = None
    outcome: TurnOutcome = TurnOutcome.ANSWERED


@dataclass
class _TurnState:
    hotels: dict[str, dict[str, Any]] = field(default_factory=dict)
    comparison: dict[str, Any] | None = None
    sources: dict[str, ContextSource] = field(default_factory=dict)
    trace: list[TraceEntry] = field(default_factory=list)
    executed_keys: set[str] = field(default_factory=set)
    executed_count: int = 0


class HotelAgent:
    def __init__(self, llm: ChatLLM, retriever: RagRetriever) -> None:
        self._llm = llm
        self._retriever = retriever

    async def run(
        self,
        message: str,
        *,
        history: list[dict[str, str]],
        session: McpSession,
        conversation_id: str | None = None,
    ) -> AgentTurnResult:
        if not message or not message.strip():
            raise AgentError("message must not be blank")
        conversation_id = conversation_id or uuid.uuid4().hex[:12]

        messages = self._build_messages(message, history)
        state = _TurnState()
        final_message, outcome = await self._conversation_loop(messages, session, state)
        if final_message is None:
            final_message = await self._force_summary(messages)

        return AgentTurnResult(
            message=final_message,
            hotels=list(state.hotels.values()),
            tool_trace=state.trace,
            conversation_id=conversation_id,
            sources=list(state.sources.values()),
            comparison=state.comparison,
            outcome=outcome,
        )

    @staticmethod
    def _build_messages(message: str, history: list[dict[str, str]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": message})
        return messages

    async def _conversation_loop(
        self,
        messages: list[dict[str, Any]],
        session: McpSession,
        state: _TurnState,
    ) -> tuple[str | None, TurnOutcome]:
        outcome = TurnOutcome.TURNS_EXHAUSTED
        for _turn in range(MAX_TURNS):
            if state.executed_count >= MAX_TOOL_CALLS:
                return None, TurnOutcome.BUDGET_EXHAUSTED
            completion = await self._llm.complete(messages, tools=AGENT_TOOLS)
            if not completion.tool_calls:
                final = await self._finalize_without_tools(messages, completion)
                if final is None:
                    raise AgentError("model did not produce a response")
                return final, TurnOutcome.ANSWERED
            messages.append(self._assistant_tool_message(completion))
            if await self._execute_tool_calls(messages, session, state, completion.tool_calls):
                return None, TurnOutcome.BUDGET_EXHAUSTED
        return None, outcome

    async def _finalize_without_tools(self, messages: list[dict[str, Any]], completion: LLMCompletion) -> str | None:
        if completion.content:
            return completion.content
        return await self._retry_for_answer(messages)

    @staticmethod
    def _assistant_tool_message(completion: LLMCompletion) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": completion.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in completion.tool_calls
            ],
        }

    @staticmethod
    def _tool_message(call_id: str, content: str) -> dict[str, Any]:
        return {"role": "tool", "tool_call_id": call_id, "content": content}

    async def _execute_tool_calls(
        self,
        messages: list[dict[str, Any]],
        session: McpSession,
        state: _TurnState,
        tool_calls: list[Any],
    ) -> bool:
        budget_hit = False
        for call in tool_calls:
            if state.executed_count >= MAX_TOOL_CALLS:
                budget_hit = True
            if budget_hit:
                messages.append(
                    self._tool_message(
                        call.id,
                        "Error: the tool budget for this turn is exhausted; this call was not executed.",
                    )
                )
                continue
            key = f"{call.name}:{canonical_arguments(call.arguments)}"
            if key in state.executed_keys:
                state.trace.append(TraceEntry(tool=call.name, status=ToolStatus.DUPLICATE))
                messages.append(
                    self._tool_message(
                        call.id,
                        f"Error: you already called {call.name} with these arguments. Use the earlier result.",
                    )
                )
                continue
            result = await execute_agent_tool(call.name, call.arguments, session, self._retriever)
            state.executed_keys.add(key)
            state.executed_count += 1
            state.trace.append(TraceEntry(tool=call.name, status=result.status))
            if result.status is ToolStatus.OK:
                state.comparison = (
                    self._collect(call.name, result.payload, state.hotels, state.sources) or state.comparison
                )
                messages.append(self._tool_message(call.id, json.dumps(result.payload, ensure_ascii=False)))
            else:
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result.payload})
        return budget_hit

    async def _retry_for_answer(self, messages: list[dict[str, Any]]) -> str | None:
        messages.append(
            {
                "role": "user",
                "content": "Please answer now based on the tool results you have. Do not call more tools.",
            }
        )
        completion = await self._llm.complete(messages, tools=None)
        return completion.content or None

    async def _force_summary(self, messages: list[dict[str, Any]]) -> str:
        messages.append(
            {
                "role": "user",
                "content": (
                    "The tool budget for this turn is exhausted. Summarize the findings so far "
                    "without calling more tools."
                ),
            }
        )
        completion = await self._llm.complete(messages, tools=None)
        if not completion.content:
            raise AgentError("model did not produce a final summary")
        return completion.content

    def _collect(
        self,
        tool_name: str,
        payload: dict[str, Any],
        hotels: dict[str, dict[str, Any]],
        sources: dict[str, ContextSource],
    ) -> dict[str, Any] | None:
        if tool_name == "search_hotels":
            for hit in payload.get("results", []):
                hotel_id = hit.get("hotel", {}).get("hotel_id")
                if hotel_id and hotel_id not in hotels:
                    hotels[hotel_id] = hit
            return None
        if tool_name == "get_hotel_details":
            hotel_id = payload.get("hotel", {}).get("hotel_id")
            if hotel_id:
                hotels[hotel_id] = payload
            return None
        if tool_name == "compare_hotels":
            return payload
        if tool_name == KNOWLEDGE_TOOL:
            for record in payload.get("sources", []):
                doc_id = record.get("doc_id")
                if not doc_id:
                    continue
                existing = sources.get(doc_id)
                if existing is None:
                    sources[doc_id] = ContextSource.model_validate(record)
                else:
                    existing.chunk_count += int(record.get("chunk_count", 1))
            return None
        return None
