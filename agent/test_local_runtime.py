"""Integration test for the locally running DebugForge AgentCore runtime."""

import json
import os
import re
import unittest
from urllib.request import Request, urlopen

from output_models.debug_code import DebuggedCodeOutput

RUNTIME_URL = os.environ.get(
    "AGENTCORE_RUNTIME_URL", "http://localhost:8080/invocations"
)
REQUEST_TIMEOUT = float(os.environ.get("AGENTCORE_TEST_TIMEOUT", "600"))


def build_prompt() -> str:
    """Build the same prompt text as server.bedrock_agent_client._build_prompt."""
    code = "def divide(a: float, b: float) -> float:\n    return a / b"
    return "\n".join(
        [
            "Here is a python code snippet to run, test, and debug:",
            "",
            "```python",
            code,
            "```",
            "",
            "Please run this code, write tests for it if none were supplied, execute the tests, "
            "identify and fix any bugs you find, and reply with the corrected working code together "
            "with an explanation of what was wrong.",
        ]
    )


def _extract_response(body: bytes, content_type: str) -> str:
    text = body.decode("utf-8")
    print("Response body:", text)
    if "text/event-stream" not in content_type:
        try:
            response = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(response, dict):
            response = response.get("response", response)
        return response if isinstance(response, str) else json.dumps(response)

    chunks = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        data = line[len("data: ") :]
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
        if isinstance(data, dict):
            data = data.get("response", json.dumps(data))
        chunks.append(data if isinstance(data, str) else json.dumps(data))
    return "".join(chunks)


class LocalRuntimeIntegrationTest(unittest.TestCase):
    def test_agent_fixes_division_by_zero_and_returns_tests(self):
        payload = json.dumps({"prompt": build_prompt()}).encode("utf-8")
        request = Request(
            RUNTIME_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            result = _extract_response(
                response.read(), response.headers.get("Content-Type", "")
            )

        self.assertTrue(result.strip(), "The runtime returned an empty response")
        output = DebuggedCodeOutput.model_validate_json(result)
        self.assertEqual(
            output.code,
            "def divide(a: float, b: float) -> float:\n    return a / b",
        )
        if output.updated_code is None:
            self.fail("The division-by-zero bug should result in updated code")
        self.assertIn("def divide", output.updated_code)
        self.assertRegex(
            output.updated_code,
            re.compile(
                r"(?:==\s*0(?:\.0)?|!=\s*0(?:\.0)?|if\s+not\s+\w+)",
                re.IGNORECASE,
            ),
            "The response should explicitly handle a zero divisor",
        )
        self.assertRegex(
            output.tests,
            re.compile(r"(?:def test_\w+|assert\s+|pytest)", re.IGNORECASE),
            "The response should include tests for the corrected function",
        )
        self.assertTrue(output.description.strip())


if __name__ == "__main__":
    unittest.main()
