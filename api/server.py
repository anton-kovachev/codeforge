import os
from collections.abc import AsyncIterable

from bedrock_agent_client import stream_debug_events, stream_pr_review_events
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from models import DebugCodeRequest, PRReviewRequest
from github_client import (
    GitHubAPIError,
    get_github_pull_request_context,
    search_github_owners,
    search_github_pull_requests,
    search_github_repositories,
)
from fastapi_clerk_auth import (
    ClerkConfig,
    ClerkHTTPBearer,
    HTTPAuthorizationCredentials,
)

# Load environment variables
load_dotenv()
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"))
clerk_guard = ClerkHTTPBearer(clerk_config)

app = FastAPI(title="DebugForge API")

# Configure CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "DebugForge API", "agent": "debugforge-agent"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/debug-code", response_class=EventSourceResponse)
async def debug_code(
    request: DebugCodeRequest,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
) -> AsyncIterable[ServerSentEvent]:
    """Stream the DebugForge agent running, testing, and fixing bugs in a code snippet.

    Emits "progress" events as the agent narrates its work, a final "result" event with the
    complete fixed code + explanation, or an "error" event if invoking the agent fails.
    """
    try:
        async for event in stream_debug_events(request):
            yield event
    except Exception as e:
        print(f"Error in debug-code endpoint: {str(e)}")
        yield ServerSentEvent(
            event="error",
            data={"error": str(e), "session_id": request.session_id or ""},
        )


@app.post("/api/review-pr", response_class=EventSourceResponse)
async def review_pr(
    request: PRReviewRequest,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
) -> AsyncIterable[ServerSentEvent]:
    """Stream todo progress and the structured review for a GitHub pull request."""
    try:
        async for event in stream_pr_review_events(request):
            yield event
    except Exception as e:
        print(f"Error in review-pr endpoint: {str(e)}")
        yield ServerSentEvent(
            event="error",
            data={"error": str(e), "session_id": request.session_id or ""},
        )


def _call_github_api(operation, *args):
    try:
        return operation(*args)
    except GitHubAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/api/github/owners/search")
def github_owner_search(
    q: str = Query(min_length=2, max_length=100),
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Search GitHub users and organizations for the PR-review project picker."""
    return {"owners": _call_github_api(search_github_owners, q)}


@app.get("/api/github/repositories/search")
def github_repository_search(
    q: str = Query(min_length=2, max_length=100),
    owner: str | None = None,
    owner_type: str | None = None,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Search GitHub repositories, optionally restricted to a selected owner."""
    if owner_type not in (None, "User", "Organization"):
        raise HTTPException(
            status_code=422,
            detail="owner_type must be User or Organization",
        )
    return {
        "repositories": _call_github_api(
            search_github_repositories,
            q,
            owner,
            owner_type,
        )
    }


@app.get("/api/github/repositories/{owner}/{repository}/pull-requests")
def github_pull_request_search(
    owner: str,
    repository: str,
    state: str = "open",
    q: str = "",
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Search PRs or list the ten most recently updated open PRs."""
    if state not in ("open", "all"):
        raise HTTPException(status_code=422, detail="state must be open or all")
    return {
        "pull_requests": _call_github_api(
            search_github_pull_requests,
            owner,
            repository,
            q,
            state,
        )
    }


@app.get(
    "/api/github/repositories/{owner}/{repository}/pull-requests/{pull_request_number}"
)
def github_pull_request_context(
    owner: str,
    repository: str,
    pull_request_number: int,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    """Fetch canonical PR and linked issue IDs after a PR is selected."""
    if pull_request_number <= 0:
        raise HTTPException(status_code=422, detail="pull_request_number must be positive")
    return _call_github_api(
        get_github_pull_request_context,
        owner,
        repository,
        pull_request_number,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
