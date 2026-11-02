import json
import os
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import BotoCoreError, ClientError

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
GITHUB_API_TIMEOUT_SECONDS = 15


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@lru_cache(maxsize=4)
def _read_github_token_secret(secret_arn: str) -> str:
    try:
        response = boto3.client("secretsmanager").get_secret_value(
            SecretId=secret_arn
        )
    except (BotoCoreError, ClientError) as exc:
        raise GitHubAPIError(
            503, "Unable to load the configured GitHub API token"
        ) from exc

    secret = response.get("SecretString")
    if not isinstance(secret, str) or not secret.strip():
        raise GitHubAPIError(503, "The configured GitHub API token secret is empty")
    return secret.strip()


def _get_github_token() -> str:
    token = os.environ.get("GITHUB_API_TOKEN")
    if token:
        return token

    secret_arn = os.environ.get("GITHUB_API_TOKEN_SECRET_ARN")
    if secret_arn:
        return _read_github_token_secret(secret_arn)

    raise GitHubAPIError(
        503,
        "Configure GITHUB_API_TOKEN locally or GITHUB_API_TOKEN_SECRET_ARN for deployment",
    )


def _github_get(
    path: str,
    params: dict[str, str | int] | None = None,
) -> dict:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{GITHUB_API_ROOT}{path}{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {_get_github_token()}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "DebugForge",
        },
    )
    try:
        with urlopen(request, timeout=GITHUB_API_TIMEOUT_SECONDS) as response:
            result = json.load(response)
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read())
            message = payload.get("message", "GitHub API request failed")
        except (json.JSONDecodeError, UnicodeDecodeError):
            message = "GitHub API request failed"
        raise GitHubAPIError(
            502,
            f"GitHub API returned HTTP {exc.code}: {message}",
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise GitHubAPIError(502, "Could not reach the GitHub API") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GitHubAPIError(502, "GitHub API returned invalid JSON") from exc

    if not isinstance(result, dict):
        raise GitHubAPIError(502, "GitHub API returned an unexpected response")
    return result


def search_github_owners(query: str) -> list[dict[str, object]]:
    response = _github_get(
        "/search/users",
        {"q": query.strip(), "per_page": 10},
    )
    items = response.get("items", [])
    return [
        {
            "id": item["id"],
            "login": item["login"],
            "type": item["type"],
            "avatar_url": item.get("avatar_url"),
            "html_url": item.get("html_url"),
        }
        for item in items
    ]


def search_github_repositories(
    query: str,
    owner: str | None = None,
    owner_type: str | None = None,
) -> list[dict[str, object]]:
    query = query.strip()
    query_parts = [query]
    if "/" not in query:
        query_parts.append("in:name")
    if owner:
        qualifier = "org" if owner_type == "Organization" else "user"
        query_parts.append(f"{qualifier}:{owner}")

    response = _github_get(
        "/search/repositories",
        {"q": " ".join(query_parts), "per_page": 10, "sort": "stars", "order": "desc"},
    )
    items = response.get("items", [])
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "full_name": item["full_name"],
            "description": item.get("description"),
            "html_url": item.get("html_url"),
            "private": item.get("private", False),
            "owner": {
                "id": item["owner"]["id"],
                "login": item["owner"]["login"],
                "type": item["owner"]["type"],
                "avatar_url": item["owner"].get("avatar_url"),
            },
        }
        for item in items
    ]


def search_github_pull_requests(
    owner: str,
    repository: str,
    query: str,
    state: str,
) -> list[dict[str, object]]:
    qualifiers = [f"repo:{owner}/{repository}", "is:pr"]
    if state == "open":
        qualifiers.append("is:open")
    if query.strip():
        qualifiers.append(query.strip())

    response = _github_get(
        "/search/issues",
        {
            "q": " ".join(qualifiers),
            "per_page": 10,
            "sort": "updated",
            "order": "desc",
        },
    )
    items = response.get("items", [])
    return [
        {
            "issue_id": item["id"],
            "issue_number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "html_url": item.get("html_url"),
            "updated_at": item.get("updated_at"),
        }
        for item in items
    ]


def get_github_pull_request_context(
    owner: str,
    repository: str,
    pull_request_number: int,
) -> dict[str, object]:
    repo_path = (
        f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
    )
    pull_request = _github_get(f"{repo_path}/pulls/{pull_request_number}")
    issue = _github_get(f"{repo_path}/issues/{pull_request_number}")
    return {
        "pull_request_id": pull_request["id"],
        "pull_request_number": pull_request["number"],
        "issue_id": issue["id"],
        "issue_number": issue["number"],
        "title": pull_request["title"],
        "state": pull_request["state"],
        "draft": pull_request.get("draft", False),
        "merged_at": pull_request.get("merged_at"),
        "html_url": pull_request["html_url"],
    }
