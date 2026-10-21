from typing import Any
from pydantic import ValidationError
from strands import Agent
from strands.hooks import (
    BeforeToolCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    AfterModelCallEvent,
    BeforeInvocationEvent,
    AfterInvocationEvent,
    MessageAddedEvent,
)
from tools import ToDoReport


class AgentHookHandler:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.todo_tool_calls = []
        self.model_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.todo_report: ToDoReport = ToDoReport(todos=[], report="")

    # ── Invocation boundaries ───────────────────────────────────────────────
    def on_before_invocation(self, event: BeforeInvocationEvent):
        pass

    def on_after_invocation(self, event: AfterInvocationEvent):
        pass

    # ── Model call boundaries ───────────────────────────────────────────────
    def on_before_model_call(self, event: BeforeModelCallEvent):
        self.model_calls += 1

    def on_after_model_call(self, event: AfterModelCallEvent):
        pass

    # ── Tool call boundaries ────────────────────────────────────────────────
    def on_before_tool_call(self, event: BeforeToolCallEvent):
        pass

    def on_after_tool_call(self, event: AfterToolCallEvent):

        if event.selected_tool:
            tool_name = event.selected_tool.tool_name
            tool_input = event.tool_use.get("input", "")
            tool_use_id = event.tool_use.get("toolUseId", None)
            output: str | dict[Any, str] | None = None
            is_error = (
                event.tool_use
                if hasattr(event, "exception") and event.exception
                else False
            )

            if tool_name in ["list_todos", "create_todos", "mark_complete_todo"]:
                # Extract the result text
                try:
                    result_content = event.result.get("content", [])
                    print(f"[Debug] result_content: {result_content}")
                    output = (
                        result_content[0].get("text", str(event.result))
                        if result_content
                        else str(event.result)
                    )
                except (AttributeError, IndexError, KeyError):
                    output = str(event.result)

                try:
                    self.todo_report = ToDoReport.model_validate_json(output)
                except ValidationError as e:
                    print(f"[Error] Failed to parse ToDoReport: {e}")

            # print(
            #     f"[After tool call]  {tool_name}({tool_input}) => {output} | error={is_error}"
            # )

            # Accumulate for the summary at invocation end
            self.todo_tool_calls.append(
                {
                    "id": tool_use_id,
                    "name": tool_name,
                    "input": tool_input,
                    "output": output,
                    "error": is_error,
                }
            )

    # ── Message added ───────────────────────────────────────────────────────
    def on_message_added(self, event: MessageAddedEvent):
        pass
        # role = (
        #     event.message.get("role", "unknown")
        #     if hasattr(event, "message")
        #     else "unknown"
        # )
        # print(f"[Message added] role={role}")

    # ── Register all hooks on the agent ────────────────────────────────────
    def register(self, agent: Agent):
        agent.add_hook(self.on_before_invocation, BeforeInvocationEvent)
        agent.add_hook(self.on_after_invocation, AfterInvocationEvent)
        agent.add_hook(self.on_before_model_call, BeforeModelCallEvent)
        agent.add_hook(self.on_after_model_call, AfterModelCallEvent)
        agent.add_hook(self.on_before_tool_call, BeforeToolCallEvent)
        agent.add_hook(self.on_after_tool_call, AfterToolCallEvent)
        agent.add_hook(self.on_message_added, MessageAddedEvent)
        return self
