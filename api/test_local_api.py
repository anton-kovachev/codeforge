"""Integration test for the locally running DebugForge API and AgentCore agent."""

import json
import os
import re
import unittest
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.request import Request, urlopen

from models import (
    DebugCodeErrorEvent,
    DebugCodeProgressEvent,
    DebugCodeResultEvent,
)

API_URL = os.environ.get("DEBUGFORGE_API_URL", "http://localhost:8000/debug-code")
REQUEST_TIMEOUT = float(os.environ.get("DEBUGFORGE_API_TEST_TIMEOUT", "600"))


def _iter_sse_events(response: Iterable[bytes]) -> Iterator[tuple[str, dict[str, Any]]]:
    event_type = "message"
    data_lines: list[str] = []

    for raw_line in response:
        print(f"Raw line: {raw_line}")
        try:
            line = raw_line.decode("utf-8").rstrip("\r\n")
        except Exception as e:
            print(f"Error decoding line: {raw_line}, error: {e}")
            continue
        print(f"Decoded line: {line}")
        if not line:
            if data_lines:
                yield event_type, json.loads("\n".join(data_lines))
            event_type = "message"
            data_lines = []

        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if not separator:
            continue
        if value.startswith(" "):
            value = value[1:]

        if field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)

    if data_lines:
        print(f"Final data lines before yielding: {data_lines}")
        yield event_type, json.loads("\n".join(data_lines))


class LocalApiIntegrationTest(unittest.TestCase):
    def test_local_api(self):
        code = "def divide(a: float, b: float) -> float:\n    return a / b"
        payload = json.dumps(
            {
                "code": code,
                "language": "python",
                "tests": None,
                "instructions": None,
            }
        ).encode("utf-8")
        request = Request(
            API_URL,
            data=payload,
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            self.assertIn(
                "text/event-stream",
                response.headers.get("Content-Type", ""),
            )
            try:
                events = list(_iter_sse_events(response))
            except Exception as e:
                self.fail(f"Failed to iterate SSE events: {e}")

        errors = [
            DebugCodeErrorEvent.model_validate(data)
            for event_type, data in events
            if event_type == "error"
        ]
        if errors:
            self.fail(f"The API returned an error: {errors[0].error}")

        progress_events = [
            DebugCodeProgressEvent.model_validate(data)
            for event_type, data in events
            if event_type == "progress"
        ]
        result_events = [
            DebugCodeResultEvent.model_validate(data)
            for event_type, data in events
            if event_type == "result"
        ]

        self.assertTrue(progress_events, "The API returned no todo progress events")
        self.assertEqual(len(result_events), 1, "Expected one final result event")

        result = result_events[0]
        self.assertTrue(result.result.code.strip())
        self.assertEqual(result.result.code, code)
        if result.result.updated_code is None:
            self.fail("The division-by-zero bug should result in updated code")
        self.assertRegex(
            result.result.updated_code,
            re.compile(
                r"(?:==\s*0(?:\.0)?|!=\s*0(?:\.0)?|if\s+not\s+\w+)",
                re.IGNORECASE,
            ),
            "The final code should explicitly handle a zero divisor",
        )
        self.assertRegex(
            result.result.tests,
            re.compile(r"(?:def test_\w+|assert\s+|pytest)", re.IGNORECASE),
            "The final response should include tests",
        )
        self.assertTrue(result.result.description.strip())

        session_ids = {event.session_id for event in progress_events}
        session_ids.add(result.session_id)
        self.assertEqual(len(session_ids), 1, "SSE events should share one session ID")


if __name__ == "__main__":
    unittest.main()
