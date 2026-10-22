from pydantic import BaseModel, Field


class DebuggedCodeOutput(BaseModel):
    """Structured result returned after the agent reviews, tests, and debugs code."""

    code: str = Field(
        description="The complete original source code exactly as provided by the user."
    )
    updated_code: str | None = Field(
        default=None,
        description=(
            "The complete corrected or improved source code when bugs were fixed or "
            "optimizations/improvements were made. Use null when the original code did "
            "not need changes."
        ),
    )
    tests: str = Field(
        description=(
            "The complete original user-provided test code. If the user supplied no "
            "tests, provide the complete tests created for verification. Tests must "
            "target updated_code when it is not null, otherwise they must target code."
        )
    )
    updated_tests: str | None = Field(
        default=None,
        description=(
            "The complete corrected or improved test code when user-provided tests "
            "needed changes. Use null when the original tests did not need changes. "
            "When not null, these tests must be the ones used to verify the final code."
        ),
    )
    description: str = Field(
        description=(
            "A comprehensive explanation of the original code's main issues and the "
            "reasoning behind every fix or improvement. Explain relevant test coverage "
            "and the observed verification results."
        )
    )
