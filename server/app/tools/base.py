"""Base classes for tool inputs and outputs."""

from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    """Base for tool inputs: frozen, and unknown keys are rejected.

    `extra="forbid"` means the LLM cannot smuggle extra fields into a
    tool call (standards/backend.md section 4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class Output(BaseModel):
    """Base for tool outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class NoArgs(Input):
    """This tool takes no arguments."""
