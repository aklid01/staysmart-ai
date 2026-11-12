from staysmart.domain.errors import StaySmartError


class LLMUnavailableError(StaySmartError):
    code = "llm_unavailable"


class AgentError(StaySmartError):
    code = "agent_error"
