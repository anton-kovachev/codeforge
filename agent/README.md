# debugforge-agent

An AWS Bedrock AgentCore agent with separate workflows to **debug code** and **review GitHub pull requests**.

It is built the same way as the `finale` agent in the `production` repo:
- [`BedrockAgentCoreApp`](https://github.com/aws/bedrock-agentcore-sdk-python) as the runtime wrapper
- A [Strands](https://strandsagents.com/) `Agent` using the `OpenAIModel` wrapper, pointed at the AWS
  Bedrock **Mantle** OpenAI-compatible endpoint (`https://bedrock-mantle.<region>.api.aws/v1`)
- `uv` + `pyproject.toml` for dependency management

## What it does

Given a code snippet (and optionally some tests), the agent:
1. Plans its work with a todo list.
2. Executes the code in a sandboxed AWS Bedrock AgentCore Code Interpreter session to observe its behavior.
3. Writes and/or runs tests (pytest) against the code.
4. Iterates on bugs it finds, re-running the code/tests until they pass.
5. Returns a structured result with the original code and tests, optional updated code and tests when changed, and a detailed explanation of the issues and fixes.

For pull request reviews, it uses a dedicated reviewer agent and GitHub MCP tools to inspect
the selected repository and PR. It returns a structured summary, actionable findings with
the exact repository-relative path, suggested code and optional tests, and a pass/fail
verdict. The GitHub MCP server is only opened for this workflow; configure `GITHUB_MCP_TOKEN`
in the agent environment.

## OpenAI trace export

Set `OPENAI_KEY` in the agent's `.env` to export workflow traces to the
[OpenAI Traces dashboard](https://platform.openai.com/traces). The agent still runs on Strands
with its configured Bedrock model; this does not convert it into an OpenAI Agents SDK agent.
Traces include workflow/session identifiers and model/tool call names, counts, and outcomes.
They intentionally exclude prompts, source code, PR content, and tool inputs/outputs. If
`OPENAI_KEY` is unset, trace export is disabled.

## Tools

- `execute_code(code, language="python")` - runs a snippet in the sandbox and returns its output.
- `run_tests(code, test_code, language="python")` - writes the source + tests into the sandbox and runs `pytest`.
- `create_todos` / `mark_complete` / `list_todos` - plan tracking, same pattern as the `finale` agent.

## Local setup

1. Copy `.env.example` to `.env` and fill in your AWS Bedrock bearer token / region / model id.
   Set `OPENAI_KEY` only if you want OpenAI trace export:
   ```
   cp .env.example .env
   ```
2. Install dependencies:
   ```
   uv sync
   ```
3. Run the agent locally:
   ```
   uv run agent.py
   ```
4. In another terminal, invoke it:
   ```
   curl -X POST http://localhost:8080/invocations \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Run, test, and debug this code.", "language": "python", "code": "def add(a, b):\n    return a - b"}'
   ```
5. To invoke a PR review, pass the workflow and repository/PR:
   ```
   curl -X POST http://localhost:8080/invocations \
     -H "Content-Type: application/json" \
     -d '{"workflow": "pr_review", "project": "owner/repository", "pull_request_number": 123}'
   ```

## Deploy to AWS Bedrock AgentCore

```
uv run agentcore configure -e agent.py
uv run agentcore launch
uv run agentcore invoke '{"prompt": "Run, test, and debug this code.", "language": "python", "code": "def add(a, b):\n    return a - b"}'
```

If your Bedrock model isn't available in your default AWS region, point `configure` at the right one, e.g.:
```
uv run agentcore configure -e agent.py --region us-west-2
```

After `launch`, note the `agent_arn` written into `.bedrock_agentcore.yaml` -
that's what the `debugforge-server` FastAPI app (in `../server`) needs in order to invoke this agent.
