import copy
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from staysmart.agent.errors import LLMUnavailableError
from staysmart.config import Settings


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMCompletion:
    content: str | None
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class ChatLLM(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMCompletion: ...


class OpenAICompatLLM:
    def __init__(self, settings: Settings) -> None:
        api_key = settings.llm_api_key or "not-needed"
        self._client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=api_key, timeout=120.0)
        self._model = settings.llm_model

    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMCompletion:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools or None,
                temperature=0.1,
            )
        except (APIConnectionError, APITimeoutError, APIStatusError, RuntimeError) as exc:
            raise LLMUnavailableError(f"LLM request failed: {type(exc).__name__}: {exc}") from exc

        choice = response.choices[0]
        message = choice.message
        tool_calls: list[LLMToolCall] = []
        for raw in message.tool_calls or []:
            try:
                arguments = json.loads(raw.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(LLMToolCall(id=raw.id, name=raw.function.name, arguments=arguments))
        content = message.content if message.content else None
        return LLMCompletion(content=content, tool_calls=tool_calls)


class ScriptedLLM:
    def __init__(self, steps: list[LLMCompletion | Exception]) -> None:
        self.steps = list(steps)
        self.requests: list[dict] = []
        self.completed_calls = 0

    async def complete(self, messages: list[dict], tools: list[dict] | None = None) -> LLMCompletion:
        self.requests.append({"messages": copy.deepcopy(messages), "tools": copy.deepcopy(tools)})
        self.completed_calls += 1
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step
