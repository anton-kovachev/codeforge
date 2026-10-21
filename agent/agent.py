import os
import uuid
from typing import Any
from mcp.client.streamable_http import streamablehttp_client

from agent_hook_handler import AgentHookHandler
from aws_bedrock_token_generator import provide_token
from bedrock_agentcore import BedrockAgentCoreApp
from dotenv import load_dotenv
from event_helpers import (
    get_todo_for_tool_call_id,
    is_tool_call_result_event,
)
from memory import configure_memory_session_manager
from output_models.debug_code import DebuggedCodeOutput
from strands import Agent
from strands.models.openai import OpenAIModel
from tools import (
    create_todos,
    execute_code,
    get_todo_report,
    list_todos,
    mark_complete_todo,
    run_tests,
)
from contextlib import ExitStack

from mcp_servers import get_agent_mcp_servers

load_dotenv(override=True)

REGION = os.environ.get("AWS_REGION", "eu-north-1")

mantle_client_args = {
    "api_key": provide_token(),
    "base_url": f"https://bedrock-mantle.{REGION}.api.aws/v1",
}
model = OpenAIModel(
    client_args=mantle_client_args,
    model_id=os.environ.get("AWS_BEDROCK_MODEL_ID", "openai.gpt-oss-120b"),
    params={"max_tokens": 2024, "temperature": 0.7},
)

system_prompt = """
You are DebugForge, an AI agent that runs, tests, and debugs code snippets submitted by users.
You plan your work with your todo tools, then carry out each step in turn.

You have access to:
- execute_code: run a snippet of code in a sandboxed interpreter tool and observe its output or errors.
- run_tests via execute_code: write source code and test code into the sandbox and execute the test suite against it using the execute_code tool.

Your plan should typically include, as separate todos:
1. Reviewing the code to understand what it is meant to do.
2. Writing Python code to execute the snippet as-is and observe its behavior or errors (prefix this todo with "Write Python code to...").
3. Writing tests for the code if none were supplied, or using the supplied tests.
4. Writing Python code to run the tests and observe which pass or fail (prefix this todo with "Write Python code to...").
5. Fixing any bugs found, then re-running the code and tests to confirm the fix, repeating until everything passes.
6. Reporting back the final, corrected code together with a clear explanation of what was wrong and what you changed.

Now use the todo list tools, create a plan, carry out the steps, and reply with the solution. 
Update the todo list on each step by tracking the todo's state and marking each todo from pending to in progress to completed until are todos are completed and the task is finished.
Track any todo that requires debugging code, running code or executing tests over the code via execute_code.
Always report (list todos) the todo states after update, including which are pending, in progress, and completed.
"""

tools = [
    get_todo_report,
    create_todos,
    mark_complete_todo,
    list_todos,
    execute_code,
    run_tests,
]
app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload, context):
    """Our Agent function"""
    user_message = payload.get("prompt")
    session_id = context.session_id or str(uuid.uuid4())
    print(f"Session ID: {session_id}")
    actor_id = payload.get("actor_id", "default")

    async with ExitStack() as stack:
        mcp_servers = [
            await stack.enter_context(mcp_server)
            for mcp_server in get_agent_mcp_servers()
        ]

        [tools.extend(mcp_server.list_tools_sync) for mcp_server in mcp_servers]
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            # session_manager=configure_memory_session_manager(session_id, actor_id),
        )
        hook_handler = AgentHookHandler(session_id=session_id)
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


if __name__ == "__main__":
    print("Starting the agent application...")
    app.run()
    print("Agent application has stopped.")
