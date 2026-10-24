# DebugForge

DebugForge is an AI-assisted code debugging product concept. It accepts a code snippet, runs it in an isolated execution environment, creates or runs tests, and streams progress and a structured debugging result back to the caller.

## Product overview

### Problem and value

Debugging short code examples can involve repeatedly reproducing a failure, identifying edge cases, writing tests, and explaining a fix. DebugForge aims to bring those steps into one workflow:

1. Submit code and optionally provide tests or debugging instructions.
2. Let an agent inspect and execute the snippet in a sandbox.
3. Run supplied tests or have the agent generate tests.
4. Receive progress events and a final result containing code, tests, and an explanation.

The intended users are developers, students, and engineering teams who want help understanding and fixing small code examples. The repository includes an early end-to-end workflow: users can submit code and tests, watch agent progress, review code and test changes independently, and accept or decline the suggested updates. It is still a prototype and is not presented as production-ready.

No pricing, service-level, or production-readiness commitments are defined in this repository.

## Architecture

```text
Browser
  └── Next.js static export (S3 website hosting)
        └── FastAPI API (/api routes, container image on Lambda, streaming Function URL)
              └── Bedrock AgentCore runtime
                    └── Strands agent + model endpoint + code interpreter
```

- **Agent (`agent/`)** — Strands agent hosted by AWS Bedrock AgentCore. It plans debugging work, executes code and tests in a Code Interpreter session, and returns a structured result.
- **API (`api/`)** — FastAPI service exposing `POST /api/debug-code` as Server-Sent Events (SSE), plus `GET /api/health`. The debug route authenticates with Clerk and invokes the configured AgentCore runtime. Terraform builds a `linux/amd64` image for an `x86_64` Lambda.
- **Frontend (`frontend/`)** — Next.js application exported as static HTML, JavaScript, and CSS and uploaded to S3. Clerk authentication runs client-side; the API remains responsible for authenticating protected requests.
- **Legacy frontend (`debugforge-frontend/`)** — the earlier Vite/React scaffold. It is not built or deployed by the current deployment script.
- **Infrastructure (`terraform/`)** — separate Terraform roots for the agent runtime, API Lambda, and frontend S3 hosting bucket.
- **Orchestration (`scripts/`)** — deployment in agent → API → frontend order and teardown in the reverse order.

## Repository layout

```text
agent/                    AgentCore agent source and configuration
api/                      FastAPI streaming API
debugforge-frontend/      Legacy Vite/React scaffold
frontend/                 Deployed Next.js static frontend
scripts/deploy.sh         Deploy all Terraform phases
scripts/destroy.sh        Destroy all Terraform phases
terraform/agent/          AgentCore runtime infrastructure
terraform/api/            ECR image, Lambda, Function URL, IAM
terraform/frontend/       Public S3 static website hosting resources
```

## Requirements

For local development:

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Node.js and [`pnpm`](https://pnpm.io/)
- AWS CLI and AWS credentials if invoking a deployed AgentCore runtime
- AgentCore/model access and credentials for the selected AWS account and region

For deployment, additionally install:

- Terraform (1.5 or newer)
- Docker (for building and pushing the API and agent images)
- AWS CLI with credentials authorized to create the listed AWS resources
- A Clerk project/JWKS endpoint for API authentication

The deployment scripts use the active AWS credential chain (`AWS_PROFILE`, SSO credentials, or environment credentials). Set `AWS_REGION` to override the default `eu-north-1`.

## Local development

### Configure the AgentCore agent

Create `agent/.env` from the example and provide the model settings and Bedrock bearer token:

```bash
cp agent/.env.example agent/.env
```

Review the example for the currently expected variables (`AWS_REGION`, `AWS_BEDROCK_MODEL_ID`, and `AWS_BEARER_TOKEN_BEDROCK`). Install and run:

```bash
cd agent
uv sync
uv run agent.py
```

The local runtime listens on port `8080`. AgentCore tools execute submitted code in a Code Interpreter session; do not treat that execution environment as a substitute for reviewing untrusted code or controlling resource usage.

### Run the API locally

In another terminal, create API configuration:

```bash
cp api/.env.example api/.env
```

Set `AGENT_RUNTIME_URL=http://localhost:8080/invocations` to use the local agent, and set `CLERK_JWKS_URL` to the JWKS endpoint for your Clerk application. Configure `CORS_ORIGINS` with the local frontend origin when using a browser.

```bash
cd api
uv sync
uv run uvicorn server:app --reload --port 8000
```

The API routes are:

- `GET /` — service information.
- `GET /api/health` — health status.
- `POST /api/debug-code` — authenticated SSE debugging endpoint.

Example request body:

```json
{
  "code": "def add(a, b):\n    return a - b\n",
  "language": "python",
  "tests": null,
  "instructions": "Check the behavior for negative numbers",
  "session_id": null
}
```

Call `/api/debug-code` with a Clerk bearer token. The stream emits `progress`, then `result` on success, or `error` on failure. Include a returned `session_id` in a later request to continue the session.

```bash
curl -N -X POST http://localhost:8000/api/debug-code \
  -H "Authorization: Bearer <clerk-session-token>" \
  -H "Content-Type: application/json" \
  -d '{"code":"def add(a, b):\n    return a - b\n"}'
```

### Run the frontend locally

The deployed Next.js frontend provides the CodeForge workspace. Set its public API base URL and Clerk publishable key; both are embedded into browser code at build time, so never put Clerk secret keys or other secrets in these variables.

```bash
cd frontend
pnpm install --frozen-lockfile
NEXT_PUBLIC_CODEFORGE_API_BASE_URL="http://localhost:8000" \
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_..." \
pnpm dev
```

The Next.js configuration uses static export, producing deployable files in `out/`:

```bash
NEXT_PUBLIC_CODEFORGE_API_BASE_URL="http://localhost:8000" \
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="pk_test_..." \
pnpm build
pnpm lint
```

The API also contains `test_local_api.py` for exercising the local API/agent flow. Review its configuration before running it, since it can execute real model and code-interpreter work and may incur AWS charges.

## Deploy to AWS

The scripts operate on the `development` environment by default. Supply the Bedrock bearer token and Clerk JWKS URL through environment variables. Keep these values out of source control and command history.

```bash
export AWS_REGION=eu-north-1
export AWS_PROFILE=your-aws-profile  # Optional when credentials are already configured

read -rsp "Bedrock bearer token: " AWS_BEARER_TOKEN_BEDROCK
printf '\n'
export AWS_BEARER_TOKEN_BEDROCK
export CLERK_JWKS_URL="https://your-clerk-domain/.well-known/jwks.json"

./scripts/deploy.sh development
```

The deployment script requires a Clerk publishable key for the static Next.js build:

```bash
export CLERK_PUBLISHABLE_KEY="pk_test_..."
```

The orchestrator:

1. Applies `terraform/agent`, then reads its runtime ARN, endpoint ARN, and endpoint name outputs.
2. Passes those values into `terraform/api`, which builds/pushes the API image and deploys the Lambda and streaming Function URL.
3. Provisions the frontend S3 website bucket, builds the Next.js frontend as a static export using the API Function URL and Clerk publishable key, and syncs `frontend/out/` to S3.
4. Prints the API and S3 website URLs.

The output values are also available directly from their Terraform roots. Each phase uses its own Terraform state and workspace. The current configuration uses local Terraform state; configure a secure remote backend before team or production use.

### Tear down

```bash
./scripts/destroy.sh development
```

The destroy script destroys frontend → API → AgentCore. It requires the same `AWS_BEARER_TOKEN_BEDROCK` and `CLERK_JWKS_URL` variables because those are required Terraform inputs. The frontend bucket and ECR repositories are configured for force deletion; bucket objects and container images can therefore be permanently deleted.

### Terraform configuration

Each phase has a `terraform.development.tfvars` example. Supply required values using environment variables or an untracked `*.tfvars` file:

- Agent: `TF_VAR_aws_bearer_token_bedrock`
- API: `TF_VAR_clerk_jwks_url`; runtime identifiers are passed by the orchestration script
- Frontend: Terraform manages the S3 website resources; `scripts/deploy.sh` builds the Next.js static export and uploads it.

Avoid committing real tokens, credentials, or sensitive user configuration. Terraform state can contain sensitive values; protect it accordingly.

## Security, privacy, and operational considerations

- The API Lambda Function URL is configured with public/no-auth invocation. The `/api/debug-code` application route uses Clerk authentication, but the function endpoint itself is publicly reachable; configure CORS and application authentication correctly. The development Terraform variables currently allow all CORS origins; restrict this to known frontend origins outside development.
- S3 website hosting grants public object reads. Only publish intended static frontend build artifacts into that bucket.
- S3 website endpoints use HTTP. Use a CDN with TLS (for example, CloudFront) for a production HTTPS website.
- Static Next.js export does not run Next.js middleware, server actions, or other server-only features. Keep authorization and access control on the API for protected operations.
- AgentCore executes submitted code in a sandbox. Apply abuse prevention, request limits, observability, and budget controls before exposing the product broadly.
- The API, model calls, AgentCore runtime, Code Interpreter, Lambda, ECR, logs, and S3 may incur AWS charges. Check current service pricing and set account budgets before deployment.
- Use test AWS accounts and non-production credentials while evaluating the project. Do not commit `.env` files, local Terraform state, or credentials.

## Business direction

DebugForge’s product hypothesis is that an interactive, test-backed explanation can make debugging assistance more actionable than a plain code completion. The intended experience is to show the debugging plan, execution/test progress, corrected code, and an explanation so users can inspect what changed.

The repository demonstrates an early end-to-end workflow, not a finished commercial product. Before a public launch, the product still needs clear supported-language and execution limits, stronger operational protections, production HTTPS delivery, monitoring, and explicit privacy, retention, and pricing policies.
