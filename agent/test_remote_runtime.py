import boto3
import json
import uuid


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


# if __name__ == "main":
test_invoke_agent_streaming()
