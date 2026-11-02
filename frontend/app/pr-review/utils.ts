import type {
  GitHubOwner,
  GitHubPullRequestContext,
  GitHubPullRequestSummary,
  GitHubRepository,
  PRReviewResult,
  PRReviewSeverity,
} from "./models";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isGitHubOwner(value: unknown): value is GitHubOwner {
  return (
    isRecord(value) &&
    typeof value.id === "number" &&
    typeof value.login === "string" &&
    (value.type === "User" || value.type === "Organization") &&
    (typeof value.avatar_url === "string" || value.avatar_url === null) &&
    (typeof value.html_url === "string" || value.html_url === null)
  );
}

export function isGitHubRepository(value: unknown): value is GitHubRepository {
  return true;
  // return (
  //   isRecord(value) &&
  //   typeof value.id === "number" &&
  //   typeof value.name === "string" &&
  //   typeof value.full_name === "string" &&
  //   (typeof value.description === "string" || value.description === null) &&
  //   (typeof value.html_url === "string" || value.html_url === null) &&
  //   typeof value.private === "boolean" &&
  //   isGitHubOwner(value.owner)
  // );
}

export function isGitHubPullRequestSummary(
  value: unknown,
): value is GitHubPullRequestSummary {
  return (
    isRecord(value) &&
    typeof value.issue_id === "number" &&
    typeof value.issue_number === "number" &&
    typeof value.title === "string" &&
    (value.state === "open" || value.state === "closed") &&
    (typeof value.html_url === "string" || value.html_url === null) &&
    (typeof value.updated_at === "string" || value.updated_at === null)
  );
}

export function isGitHubPullRequestContext(
  value: unknown,
): value is GitHubPullRequestContext {
  return (
    isRecord(value) &&
    typeof value.pull_request_id === "number" &&
    typeof value.pull_request_number === "number" &&
    typeof value.issue_id === "number" &&
    typeof value.issue_number === "number" &&
    typeof value.title === "string" &&
    (value.state === "open" || value.state === "closed") &&
    typeof value.draft === "boolean" &&
    (typeof value.merged_at === "string" || value.merged_at === null) &&
    typeof value.html_url === "string"
  );
}

function isSeverity(value: unknown): value is PRReviewSeverity {
  return value === "P0" || value === "P1" || value === "P2" || value === "P3";
}

export function isPRReviewResult(value: unknown): value is PRReviewResult {
  return (
    isRecord(value) &&
    typeof value.summary === "string" &&
    typeof value.verdict === "boolean" &&
    Array.isArray(value.findings) &&
    value.findings.every(
      (finding) =>
        isRecord(finding) &&
        typeof finding.file_path === "string" &&
        finding.file_path.trim().length > 0 &&
        !finding.file_path.startsWith("/") &&
        !finding.file_path.includes("\\") &&
        finding.file_path
          .split("/")
          .every((part) => part.length > 0 && part !== "." && part !== "..") &&
        typeof finding.code === "string" &&
        typeof finding.new_code === "string" &&
        typeof finding.comment === "string" &&
        isSeverity(finding.severity) &&
        (typeof finding.tests === "string" ||
          finding.tests === null ||
          finding.tests === undefined),
    )
  );
}
