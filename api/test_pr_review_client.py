import unittest
from unittest.mock import patch

from bedrock_agent_client import (
    _build_pr_review_prompt,
    _parse_agent_output,
    _stream_agent_events,
    stream_pr_review_events,
)
from models import PRReviewOutput, PRReviewRequest


class PRReviewClientTest(unittest.TestCase):
    def test_request_prompt_includes_project_pr_and_focus(self):
        request = PRReviewRequest(
            project="example/project",
            repository_id=123,
            pull_request_number=42,
            pull_request_id=456,
            issue_number=42,
            issue_id=789,
            focus="authorization changes",
        )

        prompt = _build_pr_review_prompt(request)

        self.assertIn("example/project", prompt)
        self.assertIn("#42", prompt)
        self.assertIn("repository ID: 123", prompt)
        self.assertIn("pull request ID: 456", prompt)
        self.assertIn("issue ID: 789", prompt)
        self.assertIn("authorization changes", prompt)

    def test_review_output_is_parsed_as_structured_result(self):
        output = _parse_agent_output(
            '{"summary":"Needs a fix","findings":[{"file_path":"src/math.py",'
            '"code":"return a - b",'
            '"new_code":"return a + b","tests":"assert add(1, 2) == 3",'
            '"comment":"The implementation subtracts instead of adding.",'
            '"severity":"P1"}],'
            '"verdict":false}'
        )

        self.assertIsInstance(output, PRReviewOutput)
        self.assertFalse(output.verdict)
        self.assertEqual(output.findings[0].file_path, "src/math.py")
        self.assertEqual(output.findings[0].new_code, "return a + b")
        self.assertEqual(output.findings[0].severity, "P1")
        self.assertEqual(output.findings[0].tests, "assert add(1, 2) == 3")

    def test_review_output_rejects_findings_without_file_path(self):
        with self.assertRaises(ValueError):
            _parse_agent_output(
                '{"summary":"Needs a fix","findings":[{"code":"return a - b",'
                '"new_code":"return a + b","comment":"Wrong operation",'
                '"severity":"P1"}],"verdict":false}'
            )

    def test_review_output_rejects_absolute_finding_path(self):
        with self.assertRaises(ValueError):
            _parse_agent_output(
                '{"summary":"Needs a fix","findings":[{"file_path":"/src/math.py",'
                '"code":"return a - b","new_code":"return a + b",'
                '"comment":"Wrong operation","severity":"P1"}],"verdict":false}'
            )

    def test_invalid_pull_request_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            PRReviewRequest(project="example/project", pull_request_number=0)

    def test_review_stream_forwards_repository_and_issue_identifiers(self):
        request = PRReviewRequest(
            project="example/project",
            repository_id=123,
            pull_request_number=42,
            pull_request_id=456,
            issue_number=42,
            issue_id=789,
            focus="authorization",
        )

        with patch("bedrock_agent_client._stream_agent_events") as stream:
            stream_pr_review_events(request)

        payload = stream.call_args.args[0]
        self.assertEqual(payload["repository_id"], 123)
        self.assertEqual(payload["pull_request_id"], 456)
        self.assertEqual(payload["issue_number"], 42)
        self.assertEqual(payload["issue_id"], 789)

    def test_review_stream_emits_progress_then_structured_result(self):
        import asyncio

        async def collect_events():
            return [
                event
                async for event in _stream_agent_events(
                    {"workflow": "pr_review"},
                    "session-id",
                )
            ]

        chunks = iter(
            [
                '{"todos":[],"report":"Reviewing PR"}',
                '{"summary":"No issues found","findings":[],"verdict":true}',
            ]
        )
        with (
            patch("bedrock_agent_client.AGENT_RUNTIME_URL", "http://localhost"),
            patch(
                "bedrock_agent_client._invoke_and_iter_chunks",
                return_value=chunks,
            ),
        ):
            events = asyncio.run(collect_events())

        self.assertEqual([event.event for event in events], ["progress", "result"])
        self.assertEqual(events[0].data["session_id"], "session-id")
        self.assertEqual(events[1].data["result"]["summary"], "No issues found")

    def test_review_stream_stops_after_structured_result(self):
        import asyncio

        consumed_after_result = False

        def chunks():
            nonlocal consumed_after_result
            yield '{"summary":"Review complete","findings":[],"verdict":true}'
            consumed_after_result = True
            raise RuntimeError("The stream continued after the final result")

        async def collect_events():
            return [
                event
                async for event in _stream_agent_events(
                    {"workflow": "pr_review"},
                    "session-id",
                )
            ]

        with (
            patch("bedrock_agent_client.AGENT_RUNTIME_URL", "http://localhost"),
            patch(
                "bedrock_agent_client._invoke_and_iter_chunks",
                return_value=chunks(),
            ) as invoke,
        ):
            events = asyncio.run(collect_events())

        self.assertEqual([event.event for event in events], ["result"])
        self.assertFalse(consumed_after_result)
        invoke.assert_called_once_with({"workflow": "pr_review"}, "session-id")

    def test_debug_stream_stops_after_structured_result(self):
        import asyncio

        consumed_after_result = False

        def chunks():
            nonlocal consumed_after_result
            yield (
                '{"code":"def add(a, b): return a + b",'
                '"tests":"assert add(1, 2) == 3","description":"Corrected addition"}'
            )
            consumed_after_result = True
            raise RuntimeError("The stream continued after the final result")

        async def collect_events():
            return [
                event
                async for event in _stream_agent_events(
                    {"workflow": "debug"},
                    "session-id",
                )
            ]

        with (
            patch("bedrock_agent_client.AGENT_RUNTIME_URL", "http://localhost"),
            patch(
                "bedrock_agent_client._invoke_and_iter_chunks",
                return_value=chunks(),
            ),
        ):
            events = asyncio.run(collect_events())

        self.assertEqual([event.event for event in events], ["result"])
        self.assertEqual(
            events[0].data["result"]["description"],
            "Corrected addition",
        )
        self.assertFalse(consumed_after_result)


if __name__ == "__main__":
    unittest.main()
