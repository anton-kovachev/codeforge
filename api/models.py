from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


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


class PRReviewRequest(BaseModel):
    """A request to review a pull request in a preset GitHub repository."""

    project: str = Field(
        ...,
        description="The GitHub repository for the selected project, in owner/repository format",
    )
    repository_id: int | None = Field(
        None, gt=0, description="GitHub's numeric ID for the repository"
    )
    pull_request_number: int = Field(..., gt=0)
    pull_request_id: int | None = Field(
        None, gt=0, description="GitHub's numeric ID for the pull request"
    )
    issue_number: int | None = Field(
        None, gt=0, description="Number of the issue associated with the pull request"
    )
    issue_id: int | None = Field(
        None, gt=0, description="GitHub's numeric ID for the associated issue"
    )
    focus: Optional[str] = Field(
        None,
        description="Optional review focus or additional context",
    )
    session_id: Optional[str] = Field(
        None, description="Optional session id to continue a previous review"
    )


class PRReviewFinding(BaseModel):
    file_path: str = Field(
        ...,
        min_length=1,
        description="Exact repository-relative path of the changed file containing the issue",
    )
    code: str
    new_code: str
    tests: Optional[str] = None
    comment: str
    severity: Literal["P0", "P1", "P2", "P3"]

    @field_validator("file_path")
    @classmethod
    def validate_repository_relative_path(cls, value: str) -> str:
        if (
            value != value.strip()
            or value.startswith("/")
            or "\\" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
        ):
            raise ValueError("file_path must be an exact repository-relative path")
        return value


class PRReviewOutput(BaseModel):
    summary: str
    findings: list[PRReviewFinding] = Field(default_factory=list)
    verdict: bool


class PRReviewResultEvent(BaseModel):
    """The structured result returned by the PR review workflow."""

    result: PRReviewOutput
    session_id: str
