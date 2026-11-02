import os
import unittest
from unittest.mock import patch

from github_client import (
    GitHubAPIError,
    get_github_pull_request_context,
    search_github_owners,
    search_github_pull_requests,
    search_github_repositories,
)


class GitHubClientTest(unittest.TestCase):
    @patch("github_client._github_get")
    def test_owner_search_returns_user_and_organization_ids(self, github_get):
        github_get.return_value = {
            "items": [
                {
                    "id": 101,
                    "login": "octo-user",
                    "type": "User",
                    "avatar_url": "https://example.test/user.png",
                    "html_url": "https://github.com/octo-user",
                },
                {
                    "id": 202,
                    "login": "octo-org",
                    "type": "Organization",
                    "avatar_url": "https://example.test/org.png",
                    "html_url": "https://github.com/octo-org",
                },
            ]
        }

        owners = search_github_owners("octo")

        self.assertEqual([owner["id"] for owner in owners], [101, 202])
        self.assertEqual(owners[1]["type"], "Organization")

    @patch("github_client._github_get")
    def test_repository_search_scopes_to_selected_owner(self, github_get):
        github_get.return_value = {
            "items": [
                {
                    "id": 303,
                    "name": "sample",
                    "full_name": "octo-org/sample",
                    "owner": {
                        "id": 202,
                        "login": "octo-org",
                        "type": "Organization",
                        "avatar_url": "https://example.test/org.png",
                    },
                }
            ]
        }

        repositories = search_github_repositories(
            "sample",
            owner="octo-org",
            owner_type="Organization",
        )

        self.assertEqual(repositories[0]["id"], 303)
        self.assertEqual(
            github_get.call_args.args[1]["q"],
            "sample in:name org:octo-org",
        )

    @patch("github_client._github_get")
    def test_direct_repository_search_preserves_owner_and_name(self, github_get):
        github_get.return_value = {"items": []}

        search_github_repositories("octo-org/sample")

        self.assertEqual(
            github_get.call_args.args[1]["q"],
            "octo-org/sample",
        )

    @patch("github_client._github_get")
    def test_open_pr_search_requests_the_latest_ten(self, github_get):
        github_get.return_value = {
            "items": [
                {
                    "id": 404,
                    "number": 17,
                    "title": "Fix issue",
                    "state": "open",
                    "html_url": "https://github.com/octo/sample/pull/17",
                    "updated_at": "2026-10-31T12:00:00Z",
                }
            ]
        }

        pull_requests = search_github_pull_requests(
            "octo",
            "sample",
            "",
            "open",
        )

        self.assertEqual(pull_requests[0]["issue_id"], 404)
        self.assertEqual(pull_requests[0]["issue_number"], 17)
        params = github_get.call_args.args[1]
        self.assertIn("is:open", params["q"])
        self.assertEqual(params["per_page"], 10)

    @patch("github_client._github_get")
    def test_pull_request_context_keeps_pr_and_issue_ids_distinct(self, github_get):
        github_get.side_effect = [
            {
                "id": 505,
                "number": 17,
                "title": "Fix issue",
                "state": "closed",
                "draft": False,
                "merged_at": "2026-10-31T12:00:00Z",
                "html_url": "https://github.com/octo/sample/pull/17",
            },
            {
                "id": 606,
                "number": 17,
            },
        ]

        context = get_github_pull_request_context("octo", "sample", 17)

        self.assertEqual(context["pull_request_id"], 505)
        self.assertEqual(context["issue_id"], 606)
        self.assertEqual(context["pull_request_number"], context["issue_number"])

    def test_missing_github_token_fails_explicitly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(GitHubAPIError, "GITHUB_API_TOKEN"):
                search_github_owners("octo")


if __name__ == "__main__":
    unittest.main()
