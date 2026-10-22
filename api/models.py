from typing import Optional

from pydantic import BaseModel, Field


class DebugCodeRequest(BaseModel):
    """A request to have the DebugForge agent run, test, and fix a code snippet."""

    code: str = Field(..., description="The source code snippet to run, test and debug")
    language: str = Field("python", description="The language the snippet is written in")
    tests: Optional[str] = Field(
        None,
        description="Optional existing test code to run against the snippet. "
        "If omitted, the agent will write its own tests.",
    )
    instructions: Optional[str] = Field(
        None,
        description="Optional extra instructions for the agent, e.g. 'focus on the edge case with empty input'",
    )
    test_instructions: Optional[str] = Field(
        None,
        description="Optional instructions for writing or running tests.",
    )
    session_id: Optional[str] = Field(
        None, description="Optional session id to continue a previous conversation with the agent"
    )


class TodoItem(BaseModel):
    """A single task tracked by the agent while processing a request."""

    description: str
    completed: bool
    order: int


class TodoReport(BaseModel):
    """The agent's current todo state, emitted as progress."""

    todos: list[TodoItem]
    report: str


class DebuggedCodeOutput(BaseModel):
    """The agent's structured final answer."""

    code: str
    updated_code: str | None = None
    tests: str
    updated_tests: str | None = None
    description: str


class DebugCodeProgressEvent(BaseModel):
    """The current todo state, sent as the agent makes progress."""

    todo_report: TodoReport
    session_id: str = Field(..., description="The session id for this request")


class DebugCodeResultEvent(BaseModel):
    """The agent's structured final answer after running, testing, and debugging the code."""

    result: DebuggedCodeOutput
    session_id: str = Field(..., description="The session id used for this request")


class DebugCodeErrorEvent(BaseModel):
    """Sent if invoking the agent fails."""

    error: str = Field(..., description="A human-readable description of what went wrong")
    session_id: str = Field(..., description="The session id used for this request")
