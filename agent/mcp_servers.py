from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamable_http_client
from mcp.client.sse import sse_client

CONTEXT7_URL = "https://mcp.context7.com/mcp"


def get_agent_mcp_servers() -> list[MCPClient]:
    context7_client = MCPClient(url=CONTEXT7_URL)
    return [context7_client]
