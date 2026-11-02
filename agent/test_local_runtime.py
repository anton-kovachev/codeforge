"""Integration test for the locally running DebugForge AgentCore runtime."""

import json
import os
import re
import unittest
from urllib.request import Request, urlopen

from output_models.debug_code import DebuggedCodeOutput
from output_models.pr_review import PRReviewOutput

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


def _extract_structured_response(
    body: bytes,
    content_type: str,
    required_fields: set[str],
) -> str:
    if "text/event-stream" not in content_type:
        return _extract_response(body, content_type)

    for line in body.decode("utf-8").splitlines():
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        try:
            candidate = json.loads(data)
        except json.JSONDecodeError:
            continue

        if isinstance(candidate, dict) and "response" in candidate:
            candidate = candidate["response"]
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except json.JSONDecodeError:
                continue
        if isinstance(candidate, dict) and required_fields.issubset(candidate):
            return json.dumps(candidate)
    return ""


class StructuredResponseTest(unittest.TestCase):
    def test_extracts_final_structured_result_after_todo_event(self):
        body = (
            'data: {"response":"{\\"todos\\":[],\\"report\\":\\"Reviewing\\"}"}\n'
            'data: {"response":"{\\"summary\\":\\"Review complete\\",'
            '\\"findings\\":[],\\"verdict\\":true}"}\n'
        ).encode("utf-8")

        result = _extract_structured_response(
            body,
            "text/event-stream",
            {"summary", "verdict"},
        )

        self.assertEqual(
            json.loads(result),
            {"summary": "Review complete", "findings": [], "verdict": True},
        )


class LocalRuntimeIntegrationTest(unittest.TestCase):
    # def test_agent_fixes_division_by_zero_and_returns_tests(self):
    #     payload = json.dumps({"prompt": build_prompt()}).encode("utf-8")
    #     request = Request(
    #         RUNTIME_URL,
    #         data=payload,
    #         headers={"Content-Type": "application/json"},
    #         method="POST",
    #     )

    #     with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
    #         result = _extract_response(
    #             response.read(), response.headers.get("Content-Type", "")
    #         )

    #     self.assertTrue(result.strip(), "The runtime returned an empty response")
    #     output = DebuggedCodeOutput.model_validate_json(result)
    #     self.assertEqual(
    #         output.code,
    #         "def divide(a: float, b: float) -> float:\n    return a / b",
    #     )
    #     if output.updated_code is None:
    #         self.fail("The division-by-zero bug should result in updated code")
    #     self.assertIn("def divide", output.updated_code)
    #     self.assertRegex(
    #         output.updated_code,
    #         re.compile(
    #             r"(?:==\s*0(?:\.0)?|!=\s*0(?:\.0)?|if\s+not\s+\w+)",
    #             re.IGNORECASE,
    #         ),
    #         "The response should explicitly handle a zero divisor",
    #     )
    #     self.assertRegex(
    #         output.tests,
    #         re.compile(r"(?:def test_\w+|assert\s+|pytest)", re.IGNORECASE),
    #         "The response should include tests for the corrected function",
    #     )
    #     self.assertTrue(output.description.strip())

    def test_pr_review_workflow_reviews_crypto_trader_pull_request(self):
        payload = json.dumps(
            {
                "workflow": "pr_review",
                "project": "anton-kovachev/crypto_trader",
                "pull_request_number": 1,
                "prompt": (
                    "Review https://github.com/anton-kovachev/crypto_trader/pull/1 "
                    "carefully using the GitHub tools. Do not post comments to the PR; "
                    "return findings in the structured result only."
                ),
            }
        ).encode("utf-8")
        request = Request(
            RUNTIME_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            result = _extract_structured_response(
                response.read(),
                response.headers.get("Content-Type", ""),
                {"summary", "verdict"},
            )

        self.assertTrue(result.strip(), "The runtime returned no PR review result")
        output = PRReviewOutput.model_validate_json(result)
        self.assertTrue(output.summary.strip())
        self.assertIsInstance(output.verdict, bool)
        for finding in output.findings:
            self.assertTrue(finding.file_path.strip())
            self.assertFalse(finding.file_path.startswith("/"))
            self.assertTrue(finding.code.strip())
            self.assertTrue(finding.new_code.strip())
            self.assertTrue(finding.comment.strip())


if __name__ == "__main__":
    unittest.main()
