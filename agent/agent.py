import json
import os
import uuid
from contextlib import ExitStack, nullcontext
from typing import Any

from agent_hook_handler import AgentHookHandler
from agents import custom_span, set_tracing_export_api_key, trace
from aws_bedrock_token_generator import provide_token
from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv
from event_helpers import (
    get_todo_for_tool_call_id,
    is_tool_call_result_event,
)
from input_guardrail import CodeInputRejected, extract_code_input, validate_code_input
from mcp_servers import get_agent_mcp_servers, get_pr_review_mcp_servers
from memory import configure_memory_session_manager
from output_models.debug_code import DebuggedCodeOutput
from output_models.pr_review import PRReviewOutput
from prompts import DEBUG_AND_TEST_CODE_SYSTEM_PROMPT, PR_REVIEW_SYSTEM_PROMPT
from review_tools import create_pr_review_todo_tools
from strands import Agent
from strands.models.openai import OpenAIModel
from tools import (
    clear_todos,
    create_todos,
    execute_code,
    get_todo_report,
    list_todos,
    mark_complete_todo,
    run_tests,
)

load_dotenv(override=True)

OPENAI_TRACING_ENABLED = bool(os.environ.get("OPENAI_KEY"))
if OPENAI_TRACING_ENABLED:
    set_tracing_export_api_key(os.environ["OPENAI_KEY"])
else:
    print("OpenAI tracing disabled: OPENAI_KEY is not configured")

REGION = os.environ.get("AWS_REGION", "eu-north-1")

mantle_client_args = {
    "api_key": provide_token(),
    "base_url": f"https://bedrock-mantle.{REGION}.api.aws/v1",
}
model = OpenAIModel(
    client_args=mantle_client_args,
    model_id=os.environ.get("AWS_BEDROCK_MODEL_ID", "openai.gpt-oss-120b"),
    params={"max_tokens": 4096, "temperature": 0.7},
)


tools = [
    get_todo_report,
    create_todos,
    mark_complete_todo,
    list_todos,
    execute_code,
    run_tests,
]
app = BedrockAgentCoreApp()


def _trace_context(workflow: str, session_id: str):
    if not OPENAI_TRACING_ENABLED:
        return nullcontext()
    return trace(
        workflow_name=f"DebugForge {workflow}",
        group_id=session_id,
        metadata={"workflow": workflow},
    )


@app.entrypoint
async def invoke(payload, context):
    """Our Agent function"""
    user_message = payload.get("prompt")
    session_id = context.session_id or str(uuid.uuid4())
    print(f"Session ID: {session_id}")
    actor_id = payload.get("actor_id", "default")

    workflow = payload.get("workflow", "debug")
    if workflow == "pr_review":
        invoke_workflow = _invoke_pr_review(payload, user_message, session_id)
    elif workflow == "debug":
        invoke_workflow = _invoke_debug(payload, session_id, actor_id)
    else:
        yield json.dumps({"error": f"Unknown workflow: {workflow}"})
        return

    async for event in invoke_workflow:
        yield event


async def _invoke_debug(payload, session_id, actor_id):
    trace_data = {
        "workflow": "debug",
        "session_id": session_id,
        "status": "running",
    }
    with _trace_context("debug", session_id):
        trace_span = (
            custom_span("Strands workflow", data=trace_data)
            if OPENAI_TRACING_ENABLED
            else nullcontext()
        )
        with trace_span:
            try:
                async for event in _run_debug_workflow(payload, session_id, actor_id):
                    yield event
            except Exception:
                trace_data["status"] = "error"
                raise
            else:
                trace_data["status"] = "completed"


async def _run_debug_workflow(payload, session_id, actor_id):
    """Run the existing debug, test, and improve workflow."""
    user_message = payload.get("prompt")
    clear_todos()

    code = payload.get("code")
    language = payload.get("language")
    if not isinstance(code, str) or not isinstance(language, str):
        try:
            code, language = extract_code_input(user_message or "")
        except CodeInputRejected as exc:
            yield json.dumps({"error": str(exc)})
            return

    try:
        await validate_code_input(code, language)
    except CodeInputRejected as exc:
        yield json.dumps({"error": str(exc)})
        return

    with ExitStack() as stack:
        mcp_servers = [
            stack.enter_context(mcp_server) for mcp_server in get_agent_mcp_servers()
        ]

        agent_tools = []
        [agent_tools.extend(mcp_server.list_tools_sync()) for mcp_server in mcp_servers]
        agent = Agent(
            model=model,
            system_prompt=DEBUG_AND_TEST_CODE_SYSTEM_PROMPT,
            tools=tools + agent_tools,
            # session_manager=configure_memory_session_manager(session_id, actor_id),
        )
        hook_handler = AgentHookHandler(
            session_id=session_id,
            tracing_enabled=OPENAI_TRACING_ENABLED,
        )
        hook_handler.register(agent)

        stream = agent.stream_async(
            user_message,
            structured_output_model=DebuggedCodeOutput,
        )
        structured_output: DebuggedCodeOutput | None = None
        async for event in stream:

            tool_call_id = is_tool_call_result_event(event)

            if tool_call_id:
                todo_tool_call = get_todo_for_tool_call_id(
                    tool_call_id,
                    hook_handler.todo_tool_calls,
                )

                if todo_tool_call is not None:
                    print(f"[Todo Report] {hook_handler.todo_report}")
                    yield hook_handler.todo_report

            if "structured_output" in event:
                structured_output = event["structured_output"]

        if structured_output is None:
            raise RuntimeError("Agent completed without producing structured output")
        yield structured_output.model_dump_json()


async def _invoke_pr_review(payload, user_message, session_id):
    trace_data = {
        "workflow": "pr_review",
        "session_id": session_id,
        "status": "running",
    }
    with _trace_context("pr_review", session_id):
        trace_span = (
            custom_span("Strands workflow", data=trace_data)
            if OPENAI_TRACING_ENABLED
            else nullcontext()
        )
        with trace_span:
            try:
                async for event in _run_pr_review_workflow(
                    payload,
                    user_message,
                    session_id,
                ):
                    yield event
            except Exception:
                trace_data["status"] = "error"
                raise
            else:
                trace_data["status"] = "completed"


async def _run_pr_review_workflow(payload, user_message, session_id):
    """Run the isolated PR review workflow and stream todo and structured result events."""
    project = payload.get("project") or payload.get("repository")
    repository_id = payload.get("repository_id")
    pull_request = payload.get("pull_request_number") or payload.get("pr_number")
    pull_request_id = payload.get("pull_request_id")
    issue_number = payload.get("issue_number")
    issue_id = payload.get("issue_id")
    focus = payload.get("focus")

    review_prompt_parts = [
        "Review the GitHub pull request for the supplied project.",
        f"Project/repository: {project}" if project else "",
        f"Repository ID: {repository_id}" if repository_id else "",
        f"Pull request: {pull_request}" if pull_request else "",
        f"Pull request ID: {pull_request_id}" if pull_request_id else "",
        (
            f"Related issue: #{issue_number} (ID {issue_id})"
            if issue_number and issue_id
            else ""
        ),
        f"Review focus: {focus}" if focus else "",
        f"Additional request: {user_message}" if user_message else "",
        "Use the connected GitHub MCP tools to identify and inspect the PR.",
    ]
    review_request = "\n".join(part for part in review_prompt_parts if part)

    with ExitStack() as stack:
        mcp_servers = [
            stack.enter_context(mcp_server)
            for mcp_server in get_pr_review_mcp_servers()
        ]
        github_tools = [
            tool for mcp_server in mcp_servers for tool in mcp_server.list_tools_sync()
        ]
        review_todo_tools = create_pr_review_todo_tools()
        agent = Agent(
            model=model,
            system_prompt=PR_REVIEW_SYSTEM_PROMPT,
            tools=review_todo_tools + github_tools,
        )
        hook_handler = AgentHookHandler(
            session_id=session_id,
            tracing_enabled=OPENAI_TRACING_ENABLED,
            todo_tool_names=(
                "list_pr_review_todos",
                "create_pr_review_todos",
                "mark_complete_pr_review_todo",
            ),
        )
        hook_handler.register(agent)

        structured_output: PRReviewOutput | None = None
        async for event in agent.stream_async(
            review_request,
            structured_output_model=PRReviewOutput,
            limits={
                "turns": 30,
                # "output_tokens": 2000,
                "structured_output_attempts": 3,
            },
        ):
            tool_call_id = is_tool_call_result_event(event)
            if tool_call_id:
                todo_tool_call = get_todo_for_tool_call_id(
                    tool_call_id,
                    hook_handler.todo_tool_calls,
                )
                if todo_tool_call is not None:
                    yield hook_handler.todo_report.model_dump_json()

            if "structured_output" in event:
                structured_output = event["structured_output"]

        if structured_output is None:
            raise RuntimeError("PR review agent completed without structured output")
        yield structured_output.model_dump_json()


if __name__ == "__main__":
    print("Starting the agent application...")
    app.run()
    print("Agent application has stopped.")
