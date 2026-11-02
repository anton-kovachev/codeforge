import boto3
import json
import uuid

from output_models.pr_review import PRReviewOutput


def build_prompt() -> str:
    """Build the same prompt text as server.bedrock_agent_client._build_prompt."""
    code = "def divide(a: float, b: float) -> float:\n    return a / b"
    return "\n".join(
        [
            "Here is a python code snippet to run, test, and debug:",
            "",
            "```python",
            code,
            "```",
            "",
            "Please run this code, write tests for it if none were supplied, execute the tests, "
            "identify and fix any bugs you find, and reply with the corrected working code together "
            "with an explanation of what was wrong.",
        ]
    )


def test_agentcore_runtime():
    print("Starting")
    client = boto3.client("bedrock-agentcore", region_name="eu-north-1")

    response = client.invoke_agent_runtime(
        agentRuntimeArn="arn:aws:bedrock-agentcore:eu-north-1:456097556049:runtime/codeforge_agent_development_runtime-EDIaQDHr3A",
        runtimeEndpointArn="arn:aws:bedrock-agentcore:eu-north-1:456097556049:runtime/codeforge_agent_development_runtime-EDIaQDHr3A/runtime-endpoint/codeforge_agent_development_runtime_endpoint",
        runtimeSessionId=str(uuid.uuid4()),  # Unique session ID per conversation
        payload=json.dumps({"prompt": build_prompt()}),
    )

    # Response body is a streaming blob
    result = json.loads(response["response"].read())
    print(json.dumps(result, indent=2))


def test_invoke_agent_streaming():
    client = boto3.client("bedrock-agentcore", region_name="eu-north-1")
    response = client.invoke_agent_runtime(
        agentRuntimeArn="arn:aws:bedrock-agentcore:eu-north-1:456097556049:runtime/codeforge_agent_development_runtime-EDIaQDHr3A",
        runtimeSessionId=str(uuid.uuid4()),  # Unique session ID per conversation
        payload=json.dumps({"prompt": build_prompt()}),
    )

    # Check the content type
    content_type = response.get("contentType", "")
    print(f"Content-Type: {content_type}")

    # Handle event-stream response
    if "event-stream" in content_type:
        stream = response["response"]

        # Iterate over each event in the stream
        for line in stream.iter_lines():
            if not line:
                continue  # Skip empty keep-alive lines

            # Decode bytes to string
            if isinstance(line, bytes):
                line = line.decode("utf-8")

            # SSE lines are prefixed with "data: "
            if line.startswith("data:"):
                data = line[len("data:") :].strip()

                # Skip the stream termination signal
                if data == "[DONE]":
                    print("\n[Stream complete]")
                    break

                try:
                    parsed = json.loads(data)
                    print(json.dumps(parsed, indent=2))
                    # Adjust key to match your agent's response shape
                    # text = (
                    #     parsed.get("output")
                    #     or parsed.get("text")
                    #     or parsed.get("content")
                    #     or str(parsed)
                    # )
                    # print(text, end="", flush=True)

                except json.JSONDecodeError:
                    # Raw text chunk — print as-is
                    print(data, end="", flush=True)

            elif line.startswith("event:"):
                event_type = line[len("event:") :].strip()
                print(f"\n[Event type: {event_type}]")

            elif line.startswith("id:"):
                pass  # SSE event ID — can be used for resumption, ignore for now
    else:
        # Fallback: non-streaming plain response
        result = json.loads(response["response"].read())
        print(result)


def _extract_pr_review_output(response) -> str:
    def normalize(candidate):
        while True:
            if isinstance(candidate, dict) and "response" in candidate:
                candidate = candidate["response"]
                continue
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                continue
            if (
                isinstance(candidate, dict)
                and {"summary", "verdict"}.issubset(candidate)
            ):
                return candidate
            return None

    content_type = response.get("contentType", "")
    if "event-stream" in content_type:
        stream = response["response"]
        for line in stream.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if data == "[DONE]":
                continue
            try:
                candidate = json.loads(data)
            except json.JSONDecodeError:
                continue
            result = normalize(candidate)
            if result is not None:
                return json.dumps(result)
        return ""

    try:
        candidate = json.loads(response["response"].read())
    except json.JSONDecodeError:
        return ""
    result = normalize(candidate)
    return json.dumps(result) if result is not None else ""


def test_extract_pr_review_output_after_todo_event():
    class Stream:
        def iter_lines(self):
            return iter(
                [
                    b'data: {"response":"{\\"todos\\":[],\\"report\\":\\"Reviewing\\"}"}',
                    b'data: {"response":"{\\"summary\\":\\"Review complete\\",'
                    b'\\"findings\\":[],\\"verdict\\":true}"}',
                ]
            )

    response = {
        "contentType": "text/event-stream",
        "response": Stream(),
    }

    result = _extract_pr_review_output(response)

    assert json.loads(result) == {
        "summary": "Review complete",
        "findings": [],
        "verdict": True,
    }


def test_pr_review_workflow_reviews_crypto_trader_pull_request():
    client = boto3.client("bedrock-agentcore", region_name="eu-north-1")
    response = client.invoke_agent_runtime(
        agentRuntimeArn="arn:aws:bedrock-agentcore:eu-north-1:456097556049:runtime/codeforge_agent_development_runtime-EDIaQDHr3A",
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(
            {
                "workflow": "pr_review",
                "project": "anton-kovachev/crypto_trader",
                "pull_request_number": 1,
                "prompt": (
                    "Review https://github.com/anton-kovachev/crypto_trader/pull/1 "
                    "carefully using the GitHub tools. Do not post comments to the PR; "
                    "return findings in the structured result only."
                ),
            }
        ),
    )

    result = _extract_pr_review_output(response)
    assert result.strip(), "The remote runtime returned no PR review result"
    output = PRReviewOutput.model_validate_json(result)
    assert output.summary.strip()
    assert isinstance(output.verdict, bool)
    for finding in output.findings:
        assert finding.file_path.strip()
        assert not finding.file_path.startswith("/")
        assert finding.code.strip()
        assert finding.new_code.strip()
        assert finding.comment.strip()


if __name__ == "__main__":
    test_invoke_agent_streaming()
    test_pr_review_workflow_reviews_crypto_trader_pull_request()
