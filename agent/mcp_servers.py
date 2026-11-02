import os

from strands.tools.mcp import MCPClient

CONTEXT7_URL = "https://mcp.context7.com/mcp"
GITHUB_URL = "https://api.githubcopilot.com/mcp"


def get_agent_mcp_servers() -> list[MCPClient]:
    return [MCPClient(url=CONTEXT7_URL)]


def get_pr_review_mcp_servers() -> list[MCPClient]:
    github_token = os.environ.get("GITHUB_MCP_TOKEN")
    if not github_token:
        raise RuntimeError("GITHUB_MCP_TOKEN is required for PR review")

    return [
        MCPClient(
            url=GITHUB_URL,
            headers={"Authorization": f"Bearer {github_token}"},
        )
    ]
