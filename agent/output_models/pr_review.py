from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PRReviewFinding(BaseModel):
    """A validated, actionable issue found in a pull request."""

    file_path: str = Field(
        min_length=1,
        description=(
            "The exact repository-relative path of the changed file containing the issue"
        ),
    )
    code: str = Field(description="The existing problematic code snippet")
    new_code: str = Field(description="A suggested code fix")
    tests: str | None = Field(
        default=None,
        description="Tests that reproduce or validate the issue, when applicable",
    )
    comment: str = Field(
        description=(
            "Explain the failure path, its impact, and why the suggested fix resolves it. "
            "Include the file and changed line range when available."
        )
    )
    severity: Literal["P0", "P1", "P2", "P3"] = Field(
        description="Finding severity: P0, P1, P2, or P3"
    )

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
    """Structured result returned by the PR review workflow."""

    summary: str = Field(description="A concise summary of the review")
    findings: list[PRReviewFinding] = Field(
        default_factory=list,
        description="Confirmed, actionable issues found in the pull request",
    )
    verdict: bool = Field(
        description="True if the pull request passed review; false if it needs changes"
    )
