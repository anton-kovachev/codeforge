import os
from collections.abc import AsyncIterable

from bedrock_agent_client import stream_debug_events
from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from models import DebugCodeRequest
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


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/debug-code", response_class=EventSourceResponse)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
