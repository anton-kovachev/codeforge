import os
import unittest
from unittest.mock import patch

from mcp_servers import get_agent_mcp_servers, get_pr_review_mcp_servers


class MCPServersTest(unittest.TestCase):
    @patch("mcp_servers.MCPClient")
    def test_debug_workflow_does_not_create_github_client(self, mcp_client):
        get_agent_mcp_servers()

        mcp_client.assert_called_once_with(url="https://mcp.context7.com/mcp")

    @patch("mcp_servers.MCPClient")
    def test_pr_review_workflow_creates_authenticated_github_client(self, mcp_client):
        with patch.dict(os.environ, {"GITHUB_MCP_TOKEN": "test-token"}):
            get_pr_review_mcp_servers()

        mcp_client.assert_called_once_with(
            url="https://api.githubcopilot.com/mcp",
            headers={"Authorization": "Bearer test-token"},
        )

    def test_pr_review_requires_github_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GITHUB_MCP_TOKEN"):
                get_pr_review_mcp_servers()


if __name__ == "__main__":
    unittest.main()
