"""The one error shape for things the user or the LLM caused."""

from pydantic import BaseModel, ConfigDict


class ToolError(BaseModel):
    """A tool or policy refusal, returned as data, never raised.

    The LLM explains it to the user and the UI renders it as a pause or
    refusal card. `rule_id` matches data/rules.yaml exactly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    rule_id: str | None = None
    message: str
