import json
import logging
import uuid
from typing import Any

from staysmart.agent.errors import AgentError
from staysmart.agent.llm import ChatLLM
from staysmart.agent.prompts import SYSTEM_PROMPT
from staysmart.agent.tools import KNOWLEDGE_TOOL, canonical_arguments, execute_agent_tool
from staysmart.domain.models import StrictModel
from staysmart.rag.models import ContextSource
from staysmart.rag.service import RagRetriever

logger = logging.getLogger("staysmart")

MAX_TURNS = 6
MAX_TOOL_CALLS = 12


class TraceEntry(StrictModel):
    tool: str
    status: str


class AgentTurnResult(StrictModel):
    message: str
    hotels: list[dict[str, Any]]
    tool_trace: list[TraceEntry]
    conversation_id: str
    sources: list[ContextSource] = []
    comparison: dict[str, Any] | None = None
    stopped_early: bool = False


class HotelAgent:
    def __init__(self, llm: ChatLLM, retriever: RagRetriever) -> None:
        self._llm = llm
        self._retriever = retriever

    async def run(
        self,
        message: str,
        *,
        history: list[dict[str, str]],
        session: Any,
        conversation_id: str | None = None,
    ) -> AgentTurnResult:
        if not message or not message.strip():
            raise AgentError("message must not be blank")
        conversation_id = conversation_id or uuid.uuid4().hex[:12]

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": message})

        hotels: dict[str, dict[str, Any]] = {}
        comparison: dict[str, Any] | None = None
        sources: dict[str, ContextSource] = {}
        trace: list[TraceEntry] = []
        executed_keys: set[str] = set()
        executed_count = 0
        final_message: str | None = None
        budget_hit = False

        for _turn in range(MAX_TURNS):
            if executed_count >= MAX_TOOL_CALLS:
                budget_hit = True
                break
            completion = await self._llm.complete(messages, tools=self._tool_specs())
            if not completion.tool_calls:
                if completion.content:
                    final_message = completion.content
                    break
                retry = await self._retry_for_answer(messages)
                if retry is not None:
                    final_message = retry
                    break
                raise AgentError("model did not produce a response")

            messages.append(
                {
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
            )
            for call in completion.tool_calls:
                if executed_count >= MAX_TOOL_CALLS:
                    budget_hit = True
                    break
                key = f"{call.name}:{canonical_arguments(call.arguments)}"
                if key in executed_keys:
                    trace.append(TraceEntry(tool=call.name, status="duplicate"))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": (
                                f"Error: you already called {call.name} with these arguments. Use the earlier result."
                            ),
                        }
                    )
                    continue
                payload, status = await execute_agent_tool(call.name, call.arguments, session, self._retriever)
                executed_keys.add(key)
                executed_count += 1
                trace.append(TraceEntry(tool=call.name, status=status))
                if status == "ok":
                    comparison = self._collect(call.name, payload, hotels, sources) or comparison
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(payload, ensure_ascii=False),
                        }
                    )
                else:
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": payload})
            if budget_hit:
                break

        if final_message is None:
            stopped_early = True
            final_message = await self._force_summary(messages)
        else:
            stopped_early = False

        return AgentTurnResult(
            message=final_message,
            hotels=list(hotels.values()),
            tool_trace=trace,
            conversation_id=conversation_id,
            sources=list(sources.values()),
            comparison=comparison,
            stopped_early=stopped_early,
        )

    def _tool_specs(self) -> list[dict]:
        from staysmart.agent.tools import AGENT_TOOLS

        return AGENT_TOOLS

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
