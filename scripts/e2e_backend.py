"""Backend harness for frontend E2E runs: real app with a scripted LLM."""

import uvicorn

from staysmart.agent.errors import LLMUnavailableError
from staysmart.agent.llm import LLMCompletion, LLMToolCall, ScriptedLLM
from staysmart.app.main import create_app
from staysmart.config import Settings, configure_logging

STAY = {"check_in": "2026-12-04", "check_out": "2026-12-07"}

SEARCH_CALL = LLMToolCall(
    id="call-1",
    name="search_hotels",
    arguments={
        "destination": "Kyoto",
        **STAY,
        "guests": 2,
        "rooms": 1,
        "max_nightly_budget": 250.0,
        "min_rating": 8.0,
        "amenities": ["WIFI", "BREAKFAST"],
        "preferences": ["quiet room"],
    },
)

COMPARE_CALL = LLMToolCall(
    id="call-2",
    name="compare_hotels",
    arguments={
        "hotel_ids": ["hotel-lis-01", "hotel-lis-02"],
        **STAY,
        "rooms": 1,
        "guests": 2,
        "preferences": ["river view"],
    },
)

KNOWLEDGE_CALL = LLMToolCall(
    id="call-3",
    name="search_knowledge",
    arguments={"query": "Are dogs allowed at the townhouse?", "hotel_id": "hotel-kyo-01"},
)

FINAL_ANSWER = (
    "Found one match for Kyoto: **Gion Machiya Stay** at 211.86 USD per night, "
    "breakfast and wifi included. Prices are mock data.\n\n"
    "### Price summary\n\n"
    "| Room | Avg / night |\n"
    "| --- | --- |\n"
    "| Tatami Double | 211.86 USD |\n\n"
    "Reference code: `STAY-2026-12`."
)

COMPARE_ANSWER = (
    "Compared two Lisbon hotels side by side. **Alfama Riverside Boutique** has the lower "
    "total price; both are mock results.\n\n"
    "| Hotel | Total |\n"
    "| --- | --- |\n"
    "| Alfama Riverside Boutique | 635.58 USD |\n"
    "| Baixa Central Hotel | 714.21 USD |"
)

KNOWLEDGE_ANSWER = (
    "Pets are allowed at Gion Machiya Stay according to the cited knowledge document; "
    "check the sources below for the grounded wording."
)

FAILURE_TRIGGER = "trigger a failure for testing"


class RepeatingLLM(ScriptedLLM):
    def __init__(self, steps: list) -> None:
        super().__init__(steps)

    async def complete(self, messages: list[dict], tools: list[dict] | None = None):
        last = messages[-1]["content"] if messages else ""
        lowered = last.lower()
        if FAILURE_TRIGGER in last:
            raise LLMUnavailableError("connection refused (scripted E2E failure)")
        if not self.steps:
            self.steps = self._steps_for(lowered)
        return await super().complete(messages, tools)

    def _steps_for(self, lowered: str) -> list:
        if "compare" in lowered:
            return [
                LLMCompletion(content=None, tool_calls=[COMPARE_CALL]),
                LLMCompletion(content=COMPARE_ANSWER, tool_calls=[]),
            ]
        if "pet" in lowered or "dog" in lowered:
            return [
                LLMCompletion(content=None, tool_calls=[KNOWLEDGE_CALL]),
                LLMCompletion(content=KNOWLEDGE_ANSWER, tool_calls=[]),
            ]
        return [
            LLMCompletion(content=None, tool_calls=[SEARCH_CALL]),
            LLMCompletion(content=FINAL_ANSWER, tool_calls=[]),
        ]


def main() -> None:
    settings = Settings(log_level="WARNING")
    configure_logging(settings.log_level)
    llm = RepeatingLLM(
        [
            LLMCompletion(content=None, tool_calls=[SEARCH_CALL]),
            LLMCompletion(content=FINAL_ANSWER, tool_calls=[]),
        ]
    )
    app = create_app(settings, llm=llm)
    uvicorn.run(app, host="127.0.0.1", port=settings.http_port, log_level="warning")


if __name__ == "__main__":
    main()
