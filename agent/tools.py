import json
import os

from pydantic import BaseModel, Field
from strands import tool
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter

REGION = os.environ.get("AWS_REGION", "eu-north-1")
code_client = CodeInterpreter(REGION)


class ToDoItem(BaseModel):
    description: str = Field(..., description="The text describing the task")
    completed: bool = Field(False, description="Whether the task is complete")
    order: int = Field(
        ...,
        description="The order of the task in the list",
    )


class ToDoReport(BaseModel):
    todos: list[ToDoItem] = Field(..., description="The list of todo items")
    report: str = Field(..., description="The formatted report of todos")


todos = []


def get_todo_report() -> ToDoReport:
    """Get a report of all todos."""
    result = ""
    for index, todo in enumerate(todos):
        completed = "X" if todo.completed else " "
        start = "[strike][green]" if todo.completed else ""
        end = "[/strike][/green]" if todo.completed else ""
        result += f"Todo #{index + 1}: [{completed}] {start}{todo.description}{end}\n"
    return ToDoReport(todos=todos, report=result)


@tool
def create_todos(descriptions: list[str]) -> ToDoReport:
    """Add new todos from a list of descriptions and return the full list"""
    for desc in descriptions:
        todos.append(ToDoItem(description=desc, completed=False, order=len(todos) + 1))
    return get_todo_report()


@tool
def mark_complete_todo(index: int) -> ToDoReport:
    """Mark complete the todo at the given position (starting from 1) and return the full list"""
    if 1 <= index <= len(todos):
        todos[index - 1].completed = True
    else:
        return get_todo_report()
    return get_todo_report()


@tool
def list_todos() -> ToDoReport:
    """Return the full list of todos with completed ones checked off"""
    return get_todo_report()


@tool
def clear_todos() -> ToDoReport:
    """Clear all todos and return the empty list"""
    todos.clear()
    return get_todo_report()


def _extract_last_result(response) -> str:
    """Pull the last structured result out of a code interpreter response stream."""
    output = []
    for event in response["stream"]:
        if "result" in event and "content" in event["result"]:
            output.append(event["result"]["content"])
    return json.dumps(output[-1]) if output else json.dumps([])


@tool
def execute_code(code: str, language: str = "python") -> str:
    """Execute a snippet of code in a sandboxed code interpreter and return its output or error.

    Args:
        code: The source code to run.
        language: The language to run it as, e.g. "python" or "javascript". Defaults to "python".
    """
    response = code_client.invoke("executeCode", {"language": language, "code": code})
    return _extract_last_result(response)


@tool
def run_tests(code: str, test_code: str, language: str = "python") -> str:
    """Write the given source code and test code into the sandbox, then run the test suite.

    For Python, the source is saved as solution.py and the tests as test_solution.py, then
    executed with pytest. Returns the combined stdout/stderr/result from running the tests.

    Args:
        code: The source code under test.
        test_code: The test code (e.g. pytest tests) that exercises the source code.
        language: The language of the code, currently only "python" is supported. Defaults to "python".
    """
    code_client.invoke(
        "writeFiles",
        {
            "content": [
                {"path": "solution.py", "text": code},
                {"path": "test_solution.py", "text": test_code},
            ]
        },
    )
    response = code_client.invoke(
        "executeCommand",
        {"command": "python -m pytest test_solution.py -v"},
    )
    return _extract_last_result(response)
