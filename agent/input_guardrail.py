import json
import os
import re

from aws_bedrock_token_generator import provide_token
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

_CODE_BLOCK_PATTERN = re.compile(
    r"```(?P<language>[A-Za-z0-9_+#.-]+)[ \t]*\r?\n(?P<code>.*?)\r?\n```",
    re.DOTALL,
)


class CodeInputRejected(ValueError):
    """Raised when submitted code does not plausibly match its declared language."""


class CodeInputAssessment(BaseModel):
    is_valid: bool
    reason: str


def extract_code_input(prompt: str) -> tuple[str, str]:
    """Extract the first language-labeled fenced code block from a legacy prompt."""
    match = _CODE_BLOCK_PATTERN.search(prompt)
    if match is None:
        raise CodeInputRejected(
            "Could not identify a language-labeled code block. Provide code in a "
            "fenced block such as ```python ... ```."
        )
    return match.group("code"), match.group("language")


async def validate_code_input(code: str, language: str) -> None:
    """Use the configured OpenAI-compatible model to assess source-language plausibility."""
    if not code.strip():
        raise CodeInputRejected("Code cannot be empty.")
    if not language.strip():
        raise CodeInputRejected("A programming language must be specified.")

    region = os.environ.get("AWS_REGION", "eu-north-1")
    model_id = os.environ.get("AWS_BEDROCK_MODEL_ID", "openai.gpt-oss-120b")
    client = AsyncOpenAI(
        api_key=provide_token(),
        base_url=f"https://bedrock-mantle.{region}.api.aws/v1",
        timeout=30,
    )
    async with client:
        response = await client.chat.completions.create(
            model=model_id,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an input guardrail for a code debugging agent. "
                        "Assess only whether the submitted snippet is plausibly code "
                        "in the declared programming language. Accept incomplete "
                        "fragments, syntax mistakes, and code containing bugs if it "
                        "is recognizably intended to be that language. Reject ordinary "
                        "prose, empty input, and code clearly written in a different "
                        "language. Do not require the code to run or be fully correct. "
                        "Return only a JSON object with boolean `is_valid` and a concise "
                        "string `reason`."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Declared language: {language}\n"
                        f"Code:\n```{language}\n{code}\n```"
                    ),
                },
            ],
        )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("The code input guardrail returned an empty assessment.")

    try:
        assessment = CodeInputAssessment.model_validate_json(content)
    except (ValidationError, ValueError) as exc:
        raise RuntimeError(
            "The code input guardrail returned an invalid assessment."
        ) from exc

    if not assessment.is_valid:
        raise CodeInputRejected(
            assessment.reason or "Input is not recognizable as the declared language."
        )
