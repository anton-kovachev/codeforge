from typing import Any


def is_tool_call_result_event(event: dict[str, Any]) -> str | None:
    if "message" in event:
        content = next(
            (
                content
                for content in event["message"].get("content", [])
                if "toolResult" in content
            ),
            None,
        )

        if content:
            tool_info = content.get("toolResult")
            return tool_info.get("toolUseId", "")

    return None


def get_todo_for_tool_call_id(
    tool_call_id: str | None,
    todo_tool_calls: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not tool_call_id:
        return None

    print("Detected a todo event.")
    tool = next(
        (
            item
            for item in todo_tool_calls
            if item.get("id") and item.get("id") == tool_call_id
        ),
        None,
    )

    if tool is None:
        return None

    print(f"Matched tool: {tool}")
    return tool
