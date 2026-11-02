export type GitHubOwner = {
  id: number;
  login: string;
  type: "User" | "Organization";
  avatar_url: string | null;
  html_url: string | null;
};

export type GitHubRepository = {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  html_url: string | null;
  private: boolean;
  owner: GitHubOwner;
};

export type GitHubPullRequestSummary = {
  issue_id: number;
  issue_number: number;
  title: string;
  state: "open" | "closed";
  html_url: string | null;
  updated_at: string | null;
};

export type GitHubPullRequestContext = {
  pull_request_id: number;
  pull_request_number: number;
  issue_id: number;
  issue_number: number;
  title: string;
  state: "open" | "closed";
  draft: boolean;
  merged_at: string | null;
  html_url: string;
};

export type PRReviewSeverity = "P0" | "P1" | "P2" | "P3";

export type PRReviewFinding = {
  file_path: string;
  code: string;
  new_code: string;
  tests?: string | null;
  comment: string;
  severity: PRReviewSeverity;
};

export type PRReviewResult = {
  summary: string;
  findings: PRReviewFinding[];
  verdict: boolean;
};
