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
            "Here are the existing tests to run against it:",
            "",
            f"```{request.language}",
            request.tests,
            "```",
        ]
    if request.instructions:
        parts += ["", f"Additional instructions: {request.instructions}"]
    parts += [
        "",
        "Please run this code, write tests for it if none were supplied, execute the tests, ",
        "identify and fix any bugs you find, and reply with the corrected working code together ",
        "identify and fix any bugs you find, and reply with the corrected working code together ",
        "with an explanation of what was wrong. In case of tests being supplied verify that they are logically and syntactically correct and that they pass. ",
        "Improve them or add more if necessary.",
    ]
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


def _parse_agent_output(chunk: str) -> TodoReport | DebuggedCodeOutput:
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

    if "error" in payload:
        raise RuntimeError(f"Agent returned an error: {payload['error']}")

    raise ValueError("Agent returned an unrecognized response payload")


def _invoke_and_iter_chunks(prompt: str, session_id: str) -> Iterator[str]:
    """Call the agent runtime and yield its response as a sequence of text chunks (blocking)."""
    if AGENT_RUNTIME_URL:
        request = Request(
            AGENT_RUNTIME_URL,
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
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
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
    )

    yield from _iter_response_chunks(
        response["response"],
        response.get("contentType", ""),
    )


# Sentinel values passed through the thread -> asyncio bridge queue below.
_DONE = object()


def stream_debug_events(
    request: DebugCodeRequest,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Invoke the DebugForge agent and stream back SSE events as it works.

    Yields "progress" events containing todo reports, followed by a "result" event containing
    the structured final answer, or an "error" event if invocation or response parsing fails.

    The underlying boto3 call is blocking, so it runs on a background thread that feeds chunks
    into an asyncio.Queue, which this async generator then drains and re-yields as SSE events.
    """
    if not AGENT_RUNTIME_URL and not AGENT_RUNTIME_ARN:
        raise RuntimeError(
            "Set AGENT_RUNTIME_URL for a local agent, or AGENT_RUNTIME_ARN for a deployed agent"
        )

    # runtimeSessionId must be at least 33 characters; a uuid4 string (36 chars) satisfies this.
    session_id = request.session_id or str(uuid.uuid4())
    prompt = _build_prompt(request)

    async def generator() -> AsyncGenerator[ServerSentEvent, None]:
        loop = asyncio.get_running_loop()
        chunk_queue: "asyncio.Queue[object]" = asyncio.Queue()

        def producer() -> None:
            try:
                for chunk in _invoke_and_iter_chunks(prompt, session_id):
                    loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)
            except (
                Exception
            ) as exc:  # noqa: BLE001 - surfaced to the client as an error event
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
            try:
                agent_output = _parse_agent_output(item)
            except (ValueError, ValidationError) as exc:
                yield ServerSentEvent(
                    event="error",
                    data={"error": str(exc), "session_id": session_id},
                )
                return

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
            result = DebugCodeResultEvent(
                result=agent_output,
                session_id=session_id,
            )
            yield ServerSentEvent(
                event="result",
                data=result.model_dump(mode="json"),
            )

        if not result_received:
            yield ServerSentEvent(
                event="error",
                data={
                    "error": "Agent stream completed without a DebuggedCodeOutput result",
                    "session_id": session_id,
                },
            )

    return generator()
