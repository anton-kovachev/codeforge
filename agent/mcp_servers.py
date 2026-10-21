from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client


def get_agent_mcp_servers() -> list[MCPClient]:
    context7_client = MCPClient(
        lambda: streamablehttp_client(
            url="https://mcp.context7.com/mcp",
            # Context7 public endpoint — no auth required
        )
    )
    return [context7_client]