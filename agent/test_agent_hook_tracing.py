import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agent_hook_handler import AgentHookHandler


class AgentHookTracingTest(unittest.TestCase):
    @patch("agent_hook_handler.custom_span")
    def test_model_call_span_records_only_call_number_and_status(self, custom_span):
        span = custom_span.return_value
        handler = AgentHookHandler(session_id="test-session", tracing_enabled=True)

        handler.on_before_model_call(SimpleNamespace())
        handler.on_after_model_call(SimpleNamespace(exception=None))

        custom_span.assert_called_once_with(
            "Strands model call",
            data={"call_number": 1, "status": "ok"},
        )
        span.start.assert_called_once_with(mark_as_current=True)
        span.finish.assert_called_once_with(reset_current=True)

    @patch("agent_hook_handler.custom_span")
    def test_tool_call_span_excludes_tool_input_and_output(self, custom_span):
        span = custom_span.return_value
        handler = AgentHookHandler(session_id="test-session", tracing_enabled=True)
        before_event = SimpleNamespace(
            selected_tool=SimpleNamespace(tool_name="execute_code"),
            tool_use={
                "toolUseId": "tool-call-1",
                "input": {"code": "private source"},
            },
        )
        after_event = SimpleNamespace(
            selected_tool=before_event.selected_tool,
            tool_use=before_event.tool_use,
            result={"content": [{"text": "private output"}]},
            exception=None,
        )

        handler.on_before_tool_call(before_event)
        handler.on_after_tool_call(after_event)

        custom_span.assert_called_once_with(
            "Strands tool call",
            data={"tool_name": "execute_code", "status": "ok"},
        )
        span.start.assert_called_once_with(mark_as_current=True)
        span.finish.assert_called_once_with(reset_current=True)

    @patch("agent_hook_handler.custom_span")
    def test_tracing_can_be_disabled(self, custom_span):
        handler = AgentHookHandler(session_id="test-session")

        handler.on_before_model_call(SimpleNamespace())
        handler.on_after_model_call(SimpleNamespace(exception=None))

        custom_span.assert_not_called()


if __name__ == "__main__":
    unittest.main()
