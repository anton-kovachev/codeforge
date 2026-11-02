"""Client for invoking the DebugForge AgentCore agent, streamed over SSE."""

import asyncio
import json
import os
import threading
import uuid
from typing import Any, AsyncGenerator, Iterator
from urllib.request import Request, urlopen

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from dotenv import load_dotenv
from fastapi.sse import ServerSentEvent
from pydantic import ValidationError

from models import (
    DebugCodeProgressEvent,
    DebugCodeRequest,
    DebugCodeResultEvent,
    DebuggedCodeOutput,
    PRReviewOutput,
    PRReviewRequest,
    PRReviewResultEvent,
    TodoReport,
)

load_dotenv()

REGION = os.environ.get("AWS_REGION", "eu-north-1")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")
AGENT_ENDPOINT_NAME = os.environ.get("AGENT_ENDPOINT_NAME", "DEFAULT")
AGENT_RUNTIME_URL = os.environ.get("AGENT_RUNTIME_URL")

_config = Config(read_timeout=900, connect_timeout=60, retries={"max_attempts": 3})
_client: BaseClient | None = None


def _build_prompt(request: DebugCodeRequest) -> str:
    """Turn a DebugCodeRequest into the natural-language prompt sent to the agent."""
    parts = [
        f"Here is a {request.language} code snippet to run, test, and debug:",
        "",
        f"```{request.language}",
        request.code,
        "```",
    ]
    if request.tests:
        parts += [
            "",
            "Here are the original tests to run against it. Preserve these in the "
            "`tests` output. If you change them, return the complete revised tests "
            "separately as `updated_tests`:",
            "",
            f"```{request.language}",
            request.tests,
            "```",
        ]
    if request.instructions:
        parts += ["", f"Additional instructions: {request.instructions}"]
    if request.test_instructions:
        parts += [
            "",
            f"Additional test instructions: {request.test_instructions}",
        ]
    parts += [
        "",
        "Please run this code, write tests for it if none were supplied, execute the tests, ",
        "identify and fix any bugs you find, and reply with the corrected working code together ",
        "identify and fix any bugs you find, and reply with the corrected working code together ",
        "with an explanation of what was wrong. In case of tests being supplied verify that they are logically and syntactically correct and that they pass. ",
        "If supplied tests need improvements, return the original tests unchanged in `tests` "
        "and the complete passing revised tests in `updated_tests`. Set `updated_tests` to "
        "null when the supplied tests need no changes. If no tests were supplied, return "
        "the generated passing tests in `tests` and set `updated_tests` to null.",
    ]
    return "\n".join(parts)


def _build_pr_review_prompt(request: PRReviewRequest) -> str:
    parts = [
        f"Review pull request #{request.pull_request_number} in {request.project}.",
        "Use the available GitHub MCP tools to inspect the PR, its complete diff, changed files, and relevant tests and source.",
    ]
    if request.repository_id is not None:
        parts.append(f"GitHub repository ID: {request.repository_id}")
    if request.pull_request_id is not None:
        parts.append(f"GitHub pull request ID: {request.pull_request_id}")
    if request.issue_number is not None:
        parts.append(f"Related issue number: {request.issue_number}")
    if request.issue_id is not None:
        parts.append(f"Related issue ID: {request.issue_id}")
    if request.focus:
        parts.append(f"Review focus: {request.focus}")
    return "\n".join(parts)


def _iter_event_stream_chunks(body: Any) -> Iterator[str]:
    """Yield each text chunk out of the agent's SSE ('data: <json>') response stream, as it arrives."""
    lines = body.iter_lines(chunk_size=1) if hasattr(body, "iter_lines") else body
    for line in lines:
        if not line:
            continue
        decoded = line.decode("utf-8") if isinstance(line, bytes) else line
        if not decoded.startswith("data:"):
            continue
        json_chunk = decoded[len("data:") :].lstrip()
        try:
            parsed = json.loads(json_chunk)
        except json.JSONDecodeError:
            yield json_chunk
            continue
        if isinstance(parsed, dict):
            parsed = parsed.get("response", parsed)
        yield (
            parsed
            if isinstance(parsed, str)
            else json.dumps(parsed, ensure_ascii=False)
        )


def _iter_response_chunks(body: Any, content_type: str) -> Iterator[str]:
    if "text/event-stream" in content_type:
        yield from _iter_event_stream_chunks(body)
        return

    raw = body.read()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        yield raw.decode("utf-8")
        return

    if isinstance(parsed, dict):
        parsed = parsed.get("response", parsed)
    yield parsed if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False)


def _get_client() -> BaseClient:
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore", region_name=REGION, config=_config)
    return _client


def _parse_agent_output(
    chunk: str,
) -> TodoReport | DebuggedCodeOutput | PRReviewOutput:
    """Parse one complete todo report or final structured agent response."""
    try:
        payload = json.loads(chunk)
    except json.JSONDecodeError as exc:
        raise ValueError("Agent returned a response that is not valid JSON") from exc

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Agent returned a JSON string with an invalid payload"
            ) from exc

    if not isinstance(payload, dict):
        raise ValueError("Agent response must be a JSON object")

    if "todos" in payload and "report" in payload:
        return TodoReport.model_validate(payload)
    if {"code", "tests", "description"}.issubset(payload):
        return DebuggedCodeOutput.model_validate(payload)
    if {"summary", "verdict"}.issubset(payload):
        return PRReviewOutput.model_validate(payload)

    if "error" in payload:
        raise RuntimeError(f"Agent returned an error: {payload['error']}")

    raise ValueError("Agent returned an unrecognized response payload")


def _invoke_and_iter_chunks(
    payload: dict[str, Any],
    session_id: str,
) -> Iterator[str]:
    """Call the agent runtime and yield its response as a sequence of text chunks (blocking)."""
    serialized_payload = json.dumps(payload).encode("utf-8")
    if AGENT_RUNTIME_URL:
        request = Request(
            AGENT_RUNTIME_URL,
            data=serialized_payload,
            headers={
                "Content-Type": "application/json",
                "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
            },
            method="POST",
        )
        with urlopen(request, timeout=_config.read_timeout) as response:
            yield from _iter_response_chunks(
                response,
                response.headers.get("Content-Type", ""),
            )
        return

    if not AGENT_RUNTIME_ARN:
        raise RuntimeError(
            "Set AGENT_RUNTIME_URL for a local agent, or AGENT_RUNTIME_ARN for a deployed agent"
        )

    response = _get_client().invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        qualifier=AGENT_ENDPOINT_NAME,
        runtimeSessionId=session_id,
        payload=serialized_payload,
    )

    response_body = response["response"]
    try:
        yield from _iter_response_chunks(
            response_body,
            response.get("contentType", ""),
        )
    finally:
        response_body.close()


# Sentinel values passed through the thread -> asyncio bridge queue below.
_DONE = object()


def _stream_agent_events(
    payload: dict[str, Any],
    session_id: str,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Invoke an agent workflow and stream todo reports and its structured result."""
    if not AGENT_RUNTIME_URL and not AGENT_RUNTIME_ARN:
        raise RuntimeError(
            "Set AGENT_RUNTIME_URL for a local agent, or AGENT_RUNTIME_ARN for a deployed agent"
        )

    async def generator() -> AsyncGenerator[ServerSentEvent, None]:
        loop = asyncio.get_running_loop()
        chunk_queue: "asyncio.Queue[object]" = asyncio.Queue()

        def producer() -> None:
            chunks: Iterator[str] | None = None
            try:
                chunks = iter(_invoke_and_iter_chunks(payload, session_id))
                for chunk in chunks:
                    try:
                        agent_output = _parse_agent_output(chunk)
                    except (RuntimeError, ValueError, ValidationError) as exc:
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, exc)
                        break

                    loop.call_soon_threadsafe(chunk_queue.put_nowait, agent_output)
                    if not isinstance(agent_output, TodoReport):
                        break
            except Exception as exc:  # noqa: BLE001 - surfaced as an error event
                loop.call_soon_threadsafe(chunk_queue.put_nowait, exc)
            finally:
                try:
                    close = getattr(chunks, "close", None) if chunks is not None else None
                    if close is not None:
                        close()
                except Exception as exc:  # noqa: BLE001 - surfaced as an error event
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, exc)
                finally:
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, _DONE)

        threading.Thread(target=producer, daemon=True).start()

        result_received = False
        while True:
            item = await chunk_queue.get()
            if item is _DONE:
                break
            if isinstance(item, Exception):
                yield ServerSentEvent(
                    event="error",
                    data={"error": str(item), "session_id": session_id},
                )
                return
            agent_output = item
            if isinstance(agent_output, TodoReport):
                progress = DebugCodeProgressEvent(
                    todo_report=agent_output,
                    session_id=session_id,
                )
                yield ServerSentEvent(
                    event="progress",
                    data=progress.model_dump(mode="json"),
                )
                continue

            result_received = True
            if isinstance(agent_output, PRReviewOutput):
                result = PRReviewResultEvent(
                    result=agent_output,
                    session_id=session_id,
                )
            else:
                result = DebugCodeResultEvent(
                    result=agent_output,
                    session_id=session_id,
                )
            yield ServerSentEvent(
                event="result",
                data=result.model_dump(mode="json"),
            )
            return

        if not result_received:
            yield ServerSentEvent(
                event="error",
                data={
                    "error": "Agent stream completed without a structured result",
                    "session_id": session_id,
                },
            )

    return generator()


def stream_debug_events(
    request: DebugCodeRequest,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Stream progress and the structured result from the debug workflow."""
    session_id = request.session_id or str(uuid.uuid4())
    payload = {
        "workflow": "debug",
        "prompt": _build_prompt(request),
        "code": request.code,
        "language": request.language,
    }
    return _stream_agent_events(payload, session_id)


def stream_pr_review_events(
    request: PRReviewRequest,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Stream progress and the structured result from the PR review workflow."""
    session_id = request.session_id or str(uuid.uuid4())
    payload = {
        "workflow": "pr_review",
        "prompt": _build_pr_review_prompt(request),
        "project": request.project,
        "repository_id": request.repository_id,
        "pull_request_number": request.pull_request_number,
        "pull_request_id": request.pull_request_id,
        "issue_number": request.issue_number,
        "issue_id": request.issue_id,
        "focus": request.focus,
    }
    return _stream_agent_events(payload, session_id)
