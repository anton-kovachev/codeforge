# debugforge-server

A FastAPI application with a single endpoint that forwards a code snippet to the
`debugforge-agent` (deployed on AWS Bedrock AgentCore) to run, test, execute, and fix bugs in it.

Structured the same way as the `super_twin/backend` FastAPI app:
- `server.py` - the FastAPI app and routes
- `lambda_handler.py` - a Mangum handler so the app can run as an AWS Lambda function
- `pyproject.toml` + `uv` for local dependency management
- `requirements.txt` + `deploy.py` to build a Lambda-compatible zip package

## Endpoint

### `POST /debug-code` (Server-Sent Events)

Request body:
```json
{
  "code": "def add(a, b):\n    return a - b\n",
  "language": "python",
  "tests": null,
  "instructions": null,
  "session_id": null
}
```

The response is a `text/event-stream` (SSE) stream (via FastAPI's native `fastapi.sse.EventSourceResponse`)
with three possible event types, so the frontend can show live progress rather than waiting for one
big response:

- `event: progress` - sent when the agent updates its todo list. `data` contains a `todo_report`
  object with `todos` and a formatted `report`, plus the `session_id`.
- `event: result` - sent with the final structured answer. `data` contains a `result` object with
  `code`, `updated_code`, `tests`, and `description`, plus the `session_id`.
- `event: error` - sent instead of `result` if invoking the agent fails. `data`: `{"error": "...", "session_id": "..."}`

Pass the `session_id` from a prior response back in to continue the same conversation with the agent.

## Test against a locally running agent

The API can call the local AgentCore HTTP endpoint directly instead of invoking the deployed
runtime through boto3:

1. In `api/.env`, set `AGENT_RUNTIME_URL=http://localhost:8080/invocations`. When this variable
   is set, it takes precedence over `AGENT_RUNTIME_ARN`; AWS credentials for the API's AgentCore
   invocation are not needed.
2. In another terminal, start the local agent:
   ```
   cd ../agent
   uv run agent.py
   ```
   The agent still needs its own configuration and credentials to access the model endpoint.
3. Start the API as described below and send a request to `http://localhost:8000/debug-code`.
4. With both processes running, test the full local API-to-agent flow:
   ```
   uv run python -m unittest test_local_api
   ```
   Run this command from the `api` directory.
   Set `DEBUGFORGE_API_URL` or `DEBUGFORGE_API_TEST_TIMEOUT` to override the test defaults.

This uses the real locally running agent, not a model or AgentCore emulator. It bypasses only the
API's remote `InvokeAgentRuntime` call.

## Local setup

1. Copy `.env.example` to `.env` and set:
   - `AWS_REGION` - the region used by the agent
   - `AGENT_RUNTIME_ARN` - the `agent_arn` from `../agent/.bedrock_agentcore.yaml` after you `agentcore launch`
   - `CORS_ORIGINS` - comma separated list of allowed origins (include your Next.js frontend's origin,
     e.g. `http://localhost:3000`)
2. For a deployed runtime, make sure your shell has AWS credentials available (e.g. `aws sso login`, or
   exported keys) - this server calls `bedrock-agentcore:InvokeAgentRuntime` via `boto3` using your
   normal AWS credential chain. For local runtime testing, set `AGENT_RUNTIME_URL` as described above
   instead; it takes precedence over `AGENT_RUNTIME_ARN`.
3. Install dependencies:
   ```
   uv sync
   ```
4. Run the server locally:
   ```
   uv run uvicorn server:app --reload --port 8000
   ```
5. Try it out (the `-N` disables curl's output buffering so you see events as they stream in):
   ```
   curl -N -X POST http://localhost:8000/debug-code \
     -H "Content-Type: application/json" \
     -d '{"code": "def add(a, b):\n    return a - b\n"}'
   ```

> **Note on Lambda:** true SSE streaming only works when running this app directly (e.g. `uvicorn`, or
> an ECS/App Runner deployment). Standard Lambda + API Gateway REST integrations buffer the full
> response before returning it, so when deployed behind Mangum the client will receive all events at
> once after the agent finishes, rather than incrementally.

## Deploy as an AWS Lambda

1. Build the deployment zip (requires Docker, to match the Lambda runtime environment):
   ```
   uv run python deploy.py
   ```
   This produces `lambda-deployment.zip`.
2. Create/update a Lambda function (Python 3.12 runtime) with handler `lambda_handler.handler`,
   upload `lambda-deployment.zip`, and set the `AWS_REGION` / `AGENT_RUNTIME_ARN` / `CORS_ORIGINS`
   environment variables on the function.
3. Give the Lambda's execution role permission to call `bedrock-agentcore:InvokeAgentRuntime` on the
   agent's ARN.
4. Put the Lambda behind API Gateway (or a Function URL) to expose `/debug-code` over HTTP.
