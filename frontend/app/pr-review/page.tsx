"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RedirectToSignIn, Show, useAuth } from "@clerk/react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { DiffEditor } from "@monaco-editor/react";
import Link from "next/link";

import type {
  GitHubOwner,
  GitHubPullRequestContext,
  GitHubPullRequestSummary,
  GitHubRepository,
  PRReviewFinding,
  PRReviewResult,
  PRReviewSeverity,
} from "./models";
import type { TodoItem } from "../workspace/models";
import { isTodoItem } from "../workspace/utils";
import {
  isGitHubOwner,
  isGitHubPullRequestContext,
  isGitHubPullRequestSummary,
  isGitHubRepository,
  isPRReviewResult,
  isRecord,
} from "./utils";

type ProjectSearchMode = "owner" | "repository";
type PullRequestState = "open" | "all";

const severityStyles: Record<PRReviewSeverity, string> = {
  P0: "border-red-200 bg-red-100 text-red-800",
  P1: "border-orange-200 bg-orange-100 text-orange-800",
  P2: "border-amber-200 bg-amber-100 text-amber-800",
  P3: "border-slate-200 bg-slate-100 text-slate-700",
};

function getErrorMessage(value: unknown, fallback: string): string {
  if (value instanceof Error && value.message) {
    return value.message;
  }
  return fallback;
}

export default function PRReviewPage() {
  const { getToken, isLoaded } = useAuth();
  const apiBaseUrl = process.env.NEXT_PUBLIC_CODEFORGE_API_BASE_URL?.replace(
    /\/+$/,
    "",
  );
  const apiRoot = apiBaseUrl ? `${apiBaseUrl}/api` : "";

  const [projectMode, setProjectMode] =
    useState<ProjectSearchMode>("repository");
  const [projectQuery, setProjectQuery] = useState("");
  const [selectedOwner, setSelectedOwner] = useState<GitHubOwner | null>(null);
  const [selectedRepository, setSelectedRepository] =
    useState<GitHubRepository | null>(null);
  const [owners, setOwners] = useState<GitHubOwner[]>([]);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const [isSearchingProjects, setIsSearchingProjects] = useState(false);
  const [projectError, setProjectError] = useState("");

  const [pullRequestQuery, setPullRequestQuery] = useState("");
  const [pullRequestState, setPullRequestState] =
    useState<PullRequestState>("open");
  const [pullRequests, setPullRequests] = useState<GitHubPullRequestSummary[]>(
    [],
  );
  const [pullRequestDropdownOpen, setPullRequestDropdownOpen] = useState(false);
  const [isSearchingPullRequests, setIsSearchingPullRequests] = useState(false);
  const [isLoadingPullRequestDetails, setIsLoadingPullRequestDetails] =
    useState(false);
  const [pullRequestSearchError, setPullRequestSearchError] = useState("");
  const [selectedPullRequest, setSelectedPullRequest] =
    useState<GitHubPullRequestContext | null>(null);

  const [focus, setFocus] = useState("");
  const [reviewResult, setReviewResult] = useState<PRReviewResult | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [reviewProgress, setReviewProgress] = useState("");
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [isReviewing, setIsReviewing] = useState(false);
  const [copiedFinding, setCopiedFinding] = useState<number | null>(null);

  const todoListRef = useRef<HTMLUListElement>(null);
  const lastCompletedTodoRef = useRef<HTMLLIElement>(null);
  const reviewControllerRef = useRef<AbortController | null>(null);
  const detailControllerRef = useRef<AbortController | null>(null);
  const lastCompletedTodoOrder = todos.reduce<number | undefined>(
    (lastCompletedOrder, todo) =>
      todo.completed ? todo.order : lastCompletedOrder,
    undefined,
  );

  const authenticatedFetch = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const token = await getToken();
      if (!token) {
        throw new Error("Your session has expired. Please sign in again.");
      }

      const headers = new Headers(init?.headers);
      headers.set("Authorization", `Bearer ${token}`);
      let response = await fetch(input, { ...init, headers });

      if (response.status === 403) {
        debugger;
        await response.body?.cancel();
        const refreshedToken = await getToken({ skipCache: true });
        if (!refreshedToken) {
          throw new Error("Your session has expired. Please sign in again.");
        }
        headers.set("Authorization", `Bearer ${refreshedToken}`);
        response = await fetch(input, { ...init, headers });
      }

      return response;
    },
    [getToken],
  );

  const getJson = useCallback(
    async (path: string, signal?: AbortSignal): Promise<unknown> => {
      if (!apiRoot) {
        throw new Error("The API URL is not configured for this frontend.");
      }
      const response = await authenticatedFetch(`${apiRoot}${path}`, {
        signal,
      });
      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null);
        const detail =
          isRecord(body) && typeof body.detail === "string"
            ? body.detail
            : `Request failed with status ${response.status}.`;
        throw new Error(detail);
      }
      return response.json();
    },
    [apiRoot, authenticatedFetch],
  );

  const resetReview = useCallback(() => {
    reviewControllerRef.current?.abort();
    reviewControllerRef.current = null;
    setReviewResult(null);
    setReviewError("");
    setReviewProgress("");
    setTodos([]);
    setIsReviewing(false);
  }, []);

  useEffect(() => {
    const list = todoListRef.current;
    const completedTodo = lastCompletedTodoRef.current;
    if (
      !isReviewing ||
      !list ||
      !completedTodo ||
      list.scrollHeight <= list.clientHeight
    ) {
      return;
    }

    const listBounds = list.getBoundingClientRect();
    const todoBounds = completedTodo.getBoundingClientRect();
    const offsetToCenter =
      todoBounds.top -
      listBounds.top -
      (list.clientHeight - todoBounds.height) / 2;

    list.scrollTo({
      top: list.scrollTop + offsetToCenter,
      behavior: "smooth",
    });
  }, [isReviewing, lastCompletedTodoOrder]);

  useEffect(() => {
    debugger;
    const query = projectQuery.trim();
    if (
      !isLoaded ||
      !projectDropdownOpen ||
      query.length < 2 ||
      (projectMode === "owner" && selectedOwner)
    ) {
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setIsSearchingProjects(true);
      setProjectError("");
      try {
        if (projectMode === "owner") {
          const params = new URLSearchParams({ q: query });
          const result = await getJson(
            `/github/owners/search?${params.toString()}`,
            controller.signal,
          );
          if (!isRecord(result) || !Array.isArray(result.owners)) {
            throw new Error(
              "GitHub returned an invalid owner search response.",
            );
          }
          setOwners(result.owners.filter(isGitHubOwner));
          setRepositories([]);
        } else {
          const params = new URLSearchParams({ q: query });
          if (selectedOwner) {
            params.set("owner", selectedOwner.login);
            params.set("owner_type", selectedOwner.type);
          }
          const result = await getJson(
            `/github/repositories/search?${params.toString()}`,
            controller.signal,
          );
          if (!isRecord(result) || !Array.isArray(result.repositories)) {
            throw new Error(
              "GitHub returned an invalid repository search response.",
            );
          }
          debugger;
          setRepositories(result.repositories.filter(isGitHubRepository));
          setOwners([]);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setProjectError(
            getErrorMessage(error, "Could not search GitHub projects."),
          );
          setOwners([]);
          setRepositories([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsSearchingProjects(false);
        }
      }
    }, 300);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [
    getJson,
    isLoaded,
    projectDropdownOpen,
    projectMode,
    projectQuery,
    selectedOwner,
  ]);

  useEffect(() => {
    const repository = selectedRepository;
    const query = pullRequestQuery.trim();
    if (!isLoaded || !pullRequestDropdownOpen || !repository) {
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(async () => {
      setIsSearchingPullRequests(true);
      setPullRequestSearchError("");
      try {
        const params = new URLSearchParams({
          state: pullRequestState,
          q: query,
        });
        const owner = encodeURIComponent(repository.owner.login);
        const name = encodeURIComponent(repository.name);
        const result = await getJson(
          `/github/repositories/${owner}/${name}/pull-requests?${params.toString()}`,
          controller.signal,
        );
        if (!isRecord(result) || !Array.isArray(result.pull_requests)) {
          throw new Error("GitHub returned an invalid pull request response.");
        }
        setPullRequests(
          result.pull_requests.filter(isGitHubPullRequestSummary),
        );
      } catch (error) {
        if (!controller.signal.aborted) {
          setPullRequestSearchError(
            getErrorMessage(error, "Could not search pull requests."),
          );
          setPullRequests([]);
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsSearchingPullRequests(false);
        }
      }
    }, 250);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [
    getJson,
    isLoaded,
    pullRequestDropdownOpen,
    pullRequestQuery,
    pullRequestState,
    selectedRepository,
  ]);

  function chooseOwner(owner: GitHubOwner) {
    resetReview();
    detailControllerRef.current?.abort();
    setSelectedOwner(owner);
    setSelectedRepository(null);
    setSelectedPullRequest(null);
    setProjectMode("repository");
    setProjectQuery("");
    setProjectDropdownOpen(false);
    setOwners([]);
    setRepositories([]);
    setIsSearchingProjects(false);
    setProjectError("");
    setPullRequestQuery("");
    setPullRequestDropdownOpen(false);
    setPullRequests([]);
    setIsSearchingPullRequests(false);
    setPullRequestSearchError("");
    setIsLoadingPullRequestDetails(false);
  }

  function chooseRepository(repository: GitHubRepository) {
    resetReview();
    detailControllerRef.current?.abort();
    setSelectedRepository(repository);
    setSelectedPullRequest(null);
    setProjectQuery(repository.full_name);
    setProjectDropdownOpen(false);
    setOwners([]);
    setRepositories([]);
    setIsSearchingProjects(false);
    setPullRequestQuery("");
    setPullRequestDropdownOpen(false);
    setPullRequests([]);
    setIsSearchingPullRequests(false);
    setPullRequestSearchError("");
    setIsLoadingPullRequestDetails(false);
  }

  async function choosePullRequest(pullRequest: GitHubPullRequestSummary) {
    if (!selectedRepository) {
      return;
    }
    resetReview();
    detailControllerRef.current?.abort();
    const controller = new AbortController();
    detailControllerRef.current = controller;
    setSelectedPullRequest(null);
    setIsLoadingPullRequestDetails(true);
    setPullRequestSearchError("");
    setPullRequestQuery(`#${pullRequest.issue_number} · ${pullRequest.title}`);
    setPullRequestDropdownOpen(false);

    try {
      const owner = encodeURIComponent(selectedRepository.owner.login);
      const name = encodeURIComponent(selectedRepository.name);
      const details = await getJson(
        `/github/repositories/${owner}/${name}/pull-requests/${pullRequest.issue_number}`,
        controller.signal,
      );
      if (!isGitHubPullRequestContext(details)) {
        throw new Error("GitHub returned incomplete pull request identifiers.");
      }
      setSelectedPullRequest(details);
    } catch (error) {
      if (!controller.signal.aborted) {
        setPullRequestSearchError(
          getErrorMessage(error, "Could not load the selected pull request."),
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingPullRequestDetails(false);
      }
    }
  }

  async function submitReview() {
    if (
      !selectedRepository ||
      !selectedPullRequest ||
      isReviewing ||
      !apiRoot
    ) {
      return;
    }

    const controller = new AbortController();
    reviewControllerRef.current = controller;
    setIsReviewing(true);
    setReviewError("");
    setReviewProgress("Starting pull request review…");
    setReviewResult(null);
    setTodos([]);
    let terminalEventReceived = false;

    try {
      await fetchEventSource(`${apiRoot}/review-pr`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          project: selectedRepository.full_name,
          repository_id: selectedRepository.id,
          pull_request_number: selectedPullRequest.pull_request_number,
          pull_request_id: selectedPullRequest.pull_request_id,
          issue_number: selectedPullRequest.issue_number,
          issue_id: selectedPullRequest.issue_id,
          focus: focus.trim() || null,
          session_id: null,
        }),
        openWhenHidden: true,
        fetch: authenticatedFetch,
        onopen: async (response) => {
          if (!response.ok) {
            const body = await response.text();
            throw new Error(
              body ||
                `PR review request failed with status ${response.status}.`,
            );
          }
        },
        onmessage: (event) => {
          if (!event.data || terminalEventReceived) {
            return;
          }
          const payload: unknown = JSON.parse(event.data);

          if (event.event === "progress") {
            const todoReport =
              isRecord(payload) && isRecord(payload.todo_report)
                ? payload.todo_report
                : null;
            if (
              !todoReport ||
              !Array.isArray(todoReport.todos) ||
              !todoReport.todos.every(isTodoItem) ||
              typeof todoReport.report !== "string"
            ) {
              throw new Error("Received an invalid PR review progress event.");
            }
            setTodos(
              [...todoReport.todos].sort(
                (first, second) => first.order - second.order,
              ),
            );
            setReviewProgress(
              todoReport.report || "Reviewing pull request…",
            );
          } else if (event.event === "result") {
            if (!isRecord(payload) || !isPRReviewResult(payload.result)) {
              throw new Error("Received an invalid PR review result.");
            }
            terminalEventReceived = true;
            setReviewResult(payload.result);
            setReviewProgress("");
          } else if (event.event === "error") {
            const message =
              isRecord(payload) && typeof payload.error === "string"
                ? payload.error
                : "The PR review service returned an error.";
            terminalEventReceived = true;
            setReviewError(message);
          }
        },
        onclose: () => {
          if (!terminalEventReceived && !controller.signal.aborted) {
            setReviewError(
              "The review stream ended before a result was received.",
            );
          }
        },
        onerror: (error) => {
          throw error;
        },
      });
    } catch (error) {
      if (!controller.signal.aborted) {
        setReviewError(
          getErrorMessage(error, "Could not complete the PR review."),
        );
      }
    } finally {
      if (reviewControllerRef.current === controller) {
        reviewControllerRef.current = null;
        setIsReviewing(false);
      }
    }
  }

  async function copySuggestedCode(finding: PRReviewFinding, index: number) {
    try {
      await navigator.clipboard.writeText(finding.new_code);
      setCopiedFinding(index);
      window.setTimeout(
        () =>
          setCopiedFinding((current) => (current === index ? null : current)),
        1800,
      );
    } catch {
      setReviewError(
        "Could not copy the suggested code. Check clipboard permissions.",
      );
    }
  }

  function clearProjectSelection() {
    resetReview();
    detailControllerRef.current?.abort();
    setSelectedOwner(null);
    setSelectedRepository(null);
    setSelectedPullRequest(null);
    setIsLoadingPullRequestDetails(false);
    setProjectQuery("");
    setProjectDropdownOpen(false);
    setOwners([]);
    setRepositories([]);
    setIsSearchingProjects(false);
    setPullRequestQuery("");
    setPullRequests([]);
    setIsSearchingPullRequests(false);
    setProjectError("");
    setPullRequestSearchError("");
    setPullRequestDropdownOpen(false);
  }

  const severityCounts = reviewResult?.findings.reduce<Record<string, number>>(
    (counts, finding) => {
      counts[finding.severity] = (counts[finding.severity] ?? 0) + 1;
      return counts;
    },
    {},
  );
  const reviewPassed =
    reviewResult?.verdict === true && reviewResult.findings.length === 0;

  return (
    <main className="flex-1 bg-[#f7f8fc] text-slate-950">
      {!isLoaded ? (
        <div className="mx-auto max-w-7xl px-6 py-16 text-sm font-medium text-slate-500">
          Loading PR review…
        </div>
      ) : (
        <>
          <Show when="signed-in">
            <section className="mx-auto w-full max-w-5xl px-5 py-10 sm:px-8 sm:py-12">
              <Link
                href="/"
                className="text-sm font-semibold text-indigo-700 hover:text-indigo-900"
              >
                ← Back to CodeForge
              </Link>
              <div className="mt-6 max-w-3xl">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-200 bg-white px-3.5 py-1.5 text-sm font-medium text-violet-700 shadow-sm">
                  <span className="h-2 w-2 rounded-full bg-violet-500" />
                  GitHub pull request review
                </div>
                <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
                  Review a pull request
                </h1>
                <p className="mt-3 text-base leading-7 text-slate-600">
                  Choose a user or organization, search its repositories, or
                  search for a repository directly. CodeForge will review the
                  selected PR and return file-specific findings. Confirmed
                  findings may also be posted as GitHub review comments; the
                  review never approves or merges the PR.
                </p>
              </div>

              <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
                <div className="grid gap-6">
                  <div>
                    <label
                      className="block text-sm font-semibold text-slate-800"
                      htmlFor="project-search"
                    >
                      Project
                    </label>
                    <div className="mt-3 inline-flex rounded-lg bg-slate-100 p-1">
                      <button
                        type="button"
                        aria-pressed={projectMode === "owner"}
                        onClick={() => {
                          resetReview();
                          detailControllerRef.current?.abort();
                          setProjectMode("owner");
                          setSelectedOwner(null);
                          setSelectedRepository(null);
                          setSelectedPullRequest(null);
                          setIsLoadingPullRequestDetails(false);
                          setProjectQuery("");
                          setProjectDropdownOpen(false);
                          setOwners([]);
                          setRepositories([]);
                          setIsSearchingProjects(false);
                          setPullRequestQuery("");
                          setPullRequests([]);
                          setIsSearchingPullRequests(false);
                          setProjectError("");
                          setPullRequestSearchError("");
                          setProjectError("");
                          setPullRequestSearchError("");
                        }}
                        className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
                          projectMode === "owner"
                            ? "bg-white text-indigo-700 shadow-sm"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        Search user / organization
                      </button>
                      <button
                        type="button"
                        aria-pressed={projectMode === "repository"}
                        onClick={() => {
                          resetReview();
                          detailControllerRef.current?.abort();
                          setProjectMode("repository");
                          setSelectedOwner(null);
                          setSelectedRepository(null);
                          setSelectedPullRequest(null);
                          setIsLoadingPullRequestDetails(false);
                          setProjectQuery("");
                          setProjectDropdownOpen(false);
                          setPullRequestQuery("");
                        }}
                        className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
                          projectMode === "repository"
                            ? "bg-white text-indigo-700 shadow-sm"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        Search repository directly
                      </button>
                    </div>

                    {selectedOwner && projectMode === "repository" && (
                      <div className="mt-3 flex items-center gap-2 text-sm text-slate-600">
                        <span>
                          Repositories owned by{" "}
                          <strong className="text-slate-900">
                            {selectedOwner.login}
                          </strong>
                        </span>
                        <button
                          type="button"
                          className="font-semibold text-indigo-700 hover:text-indigo-900"
                          onClick={() => {
                            resetReview();
                            setSelectedOwner(null);
                            setSelectedRepository(null);
                            setSelectedPullRequest(null);
                            setProjectQuery("");
                            setRepositories([]);
                            setPullRequests([]);
                            setIsLoadingPullRequestDetails(false);
                          }}
                        >
                          Clear owner
                        </button>
                      </div>
                    )}

                    <div className="relative mt-3">
                      <input
                        id="project-search"
                        type="search"
                        value={projectQuery}
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded={projectDropdownOpen}
                        aria-controls="project-results"
                        aria-label={
                          projectMode === "owner"
                            ? "Search GitHub users and organizations"
                            : "Search GitHub repositories"
                        }
                        onFocus={() => setProjectDropdownOpen(true)}
                        onChange={(event) => {
                          const value = event.target.value;
                          setProjectQuery(value);
                          setProjectDropdownOpen(true);
                          setProjectError("");
                          if (
                            selectedRepository &&
                            value !== selectedRepository.full_name
                          ) {
                            resetReview();
                            detailControllerRef.current?.abort();
                            setSelectedRepository(null);
                            setSelectedPullRequest(null);
                            setIsLoadingPullRequestDetails(false);
                            setPullRequestQuery("");
                            setPullRequests([]);
                          }
                          setOwners([]);
                          setRepositories([]);
                          setIsSearchingProjects(false);
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") {
                            setProjectDropdownOpen(false);
                          }
                        }}
                        placeholder={
                          projectMode === "owner"
                            ? "Search by username or organization"
                            : selectedOwner
                              ? "Search repositories for this owner"
                              : "Search by repository name or owner/repository"
                        }
                        className="h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100"
                      />
                      {projectDropdownOpen &&
                        projectQuery.trim().length >= 2 && (
                          <div
                            id="project-results"
                            role="listbox"
                            aria-label="GitHub project search results"
                            className="absolute z-20 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
                          >
                            {isSearchingProjects && (
                              <p className="px-3 py-3 text-sm text-slate-500">
                                Searching GitHub…
                              </p>
                            )}
                            {!isSearchingProjects &&
                              projectMode === "owner" &&
                              owners.length === 0 && (
                                <p className="px-3 py-3 text-sm text-slate-500">
                                  No matching users or organizations.
                                </p>
                              )}
                            {!isSearchingProjects &&
                              projectMode === "owner" &&
                              owners.map((owner) => (
                                <button
                                  key={`${owner.type}-${owner.id}`}
                                  type="button"
                                  role="option"
                                  aria-selected={false}
                                  onClick={() => chooseOwner(owner)}
                                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-indigo-50 focus:bg-indigo-50 focus:outline-none"
                                >
                                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
                                    {owner.login.slice(0, 1).toUpperCase()}
                                  </span>
                                  <span className="min-w-0 flex-1">
                                    <span className="block truncate text-sm font-semibold text-slate-900">
                                      {owner.login}
                                    </span>
                                    <span className="block text-xs text-slate-500">
                                      {owner.type}
                                    </span>
                                  </span>
                                  <span className="text-xs font-medium text-indigo-700">
                                    Select owner
                                  </span>
                                </button>
                              ))}
                            {!isSearchingProjects &&
                              projectMode === "repository" &&
                              repositories.length === 0 && (
                                <p className="px-3 py-3 text-sm text-slate-500">
                                  No matching repositories.
                                </p>
                              )}
                            {!isSearchingProjects &&
                              projectMode === "repository" &&
                              repositories.map((repository) => (
                                <button
                                  key={repository.id}
                                  type="button"
                                  role="option"
                                  aria-selected={false}
                                  onClick={() => chooseRepository(repository)}
                                  className="w-full rounded-lg px-3 py-2.5 text-left hover:bg-indigo-50 focus:bg-indigo-50 focus:outline-none"
                                >
                                  <span className="flex items-center justify-between gap-3">
                                    <span className="truncate text-sm font-semibold text-slate-900">
                                      {repository.full_name}
                                    </span>
                                    {repository.private && (
                                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                                        Private
                                      </span>
                                    )}
                                  </span>
                                  {repository.description && (
                                    <span className="mt-1 block line-clamp-2 text-xs leading-5 text-slate-500">
                                      {repository.description}
                                    </span>
                                  )}
                                </button>
                              ))}
                          </div>
                        )}
                    </div>
                    {projectError && (
                      <p role="alert" className="mt-2 text-sm text-red-700">
                        {projectError}
                      </p>
                    )}
                    {selectedRepository && (
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-indigo-50 px-3.5 py-3 text-sm">
                        <span className="font-semibold text-indigo-950">
                          {selectedRepository.full_name}
                          <span className="ml-2 font-normal text-indigo-700">
                            Repository ID {selectedRepository.id}
                          </span>
                        </span>
                        <button
                          type="button"
                          onClick={clearProjectSelection}
                          className="font-semibold text-indigo-700 hover:text-indigo-950"
                        >
                          Change project
                        </button>
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="flex flex-wrap items-end justify-between gap-3">
                      <div className="flex-1">
                        <label
                          className="block text-sm font-semibold text-slate-800"
                          htmlFor="pull-request-search"
                        >
                          Pull request
                        </label>
                        <p className="mt-1 text-xs text-slate-500">
                          {pullRequestState === "open"
                            ? "Open PRs are shown by default, with the ten most recently updated first."
                            : "Search open and closed/merged PRs."}
                        </p>
                      </div>
                      <div
                        role="group"
                        aria-label="Pull request state filter"
                        className="inline-flex rounded-lg bg-slate-100 p-1"
                      >
                        <button
                          type="button"
                          aria-pressed={pullRequestState === "open"}
                          disabled={!selectedRepository}
                          onClick={() => {
                            resetReview();
                            setPullRequestState("open");
                            setSelectedPullRequest(null);
                            setPullRequestQuery("");
                            setPullRequests([]);
                            setIsSearchingPullRequests(false);
                          }}
                          className={`rounded-md px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                            pullRequestState === "open"
                              ? "bg-white text-indigo-700 shadow-sm"
                              : "text-slate-600 hover:text-slate-900"
                          }`}
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          aria-pressed={pullRequestState === "all"}
                          disabled={!selectedRepository}
                          onClick={() => {
                            resetReview();
                            setPullRequestState("all");
                            setSelectedPullRequest(null);
                            setPullRequestQuery("");
                            setPullRequests([]);
                            setIsSearchingPullRequests(false);
                          }}
                          className={`rounded-md px-3 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                            pullRequestState === "all"
                              ? "bg-white text-indigo-700 shadow-sm"
                              : "text-slate-600 hover:text-slate-900"
                          }`}
                        >
                          Open &amp; closed
                        </button>
                      </div>
                    </div>
                    <div className="relative mt-3">
                      <input
                        id="pull-request-search"
                        type="search"
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded={pullRequestDropdownOpen}
                        aria-controls="pull-request-results"
                        aria-label="Search pull requests"
                        disabled={!selectedRepository}
                        value={pullRequestQuery}
                        onFocus={() => {
                          if (selectedRepository) {
                            setPullRequestDropdownOpen(true);
                          }
                        }}
                        onChange={(event) => {
                          resetReview();
                          setSelectedPullRequest(null);
                          setPullRequestQuery(event.target.value);
                          setPullRequests([]);
                          setIsSearchingPullRequests(false);
                          setPullRequestDropdownOpen(true);
                          setPullRequestSearchError("");
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") {
                            setPullRequestDropdownOpen(false);
                          }
                        }}
                        placeholder={
                          selectedRepository
                            ? "Search by PR title or number"
                            : "Select a repository first"
                        }
                        className="h-12 w-full rounded-lg border border-slate-300 bg-white px-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-50"
                      />
                      {pullRequestDropdownOpen && selectedRepository && (
                        <div
                          id="pull-request-results"
                          role="listbox"
                          aria-label="Pull request search results"
                          className="absolute z-20 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
                        >
                          {isSearchingPullRequests && (
                            <p className="px-3 py-3 text-sm text-slate-500">
                              Searching pull requests…
                            </p>
                          )}
                          {!isSearchingPullRequests &&
                            pullRequests.length === 0 && (
                              <p className="px-3 py-3 text-sm text-slate-500">
                                No matching pull requests.
                              </p>
                            )}
                          {!isSearchingPullRequests &&
                            pullRequests.map((pullRequest) => (
                              <button
                                key={pullRequest.issue_id}
                                type="button"
                                role="option"
                                aria-selected={false}
                                onClick={() =>
                                  void choosePullRequest(pullRequest)
                                }
                                className="w-full rounded-lg px-3 py-2.5 text-left hover:bg-indigo-50 focus:bg-indigo-50 focus:outline-none"
                              >
                                <span className="flex items-center gap-2">
                                  <span className="text-xs font-semibold text-slate-500">
                                    #{pullRequest.issue_number}
                                  </span>
                                  <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-900">
                                    {pullRequest.title}
                                  </span>
                                  <span
                                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                      pullRequest.state === "open"
                                        ? "bg-emerald-100 text-emerald-800"
                                        : "bg-slate-100 text-slate-700"
                                    }`}
                                  >
                                    {pullRequest.state}
                                  </span>
                                </span>
                              </button>
                            ))}
                        </div>
                      )}
                    </div>
                    {pullRequestSearchError && (
                      <p role="alert" className="mt-2 text-sm text-red-700">
                        {pullRequestSearchError}
                      </p>
                    )}
                    {isLoadingPullRequestDetails && (
                      <p role="status" className="mt-2 text-sm text-slate-500">
                        Loading PR and linked issue identifiers…
                      </p>
                    )}
                    {selectedPullRequest && (
                      <div className="mt-3 rounded-lg bg-slate-50 px-3.5 py-3 text-sm text-slate-700">
                        <p className="font-semibold text-slate-900">
                          #{selectedPullRequest.pull_request_number}{" "}
                          {selectedPullRequest.title}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          PR ID {selectedPullRequest.pull_request_id} · Issue #
                          {selectedPullRequest.issue_number} · Issue ID{" "}
                          {selectedPullRequest.issue_id}
                          {selectedPullRequest.draft ? " · Draft" : ""}
                          {selectedPullRequest.merged_at ? " · Merged" : ""}
                        </p>
                      </div>
                    )}
                  </div>

                  <div>
                    <label
                      className="block text-sm font-semibold text-slate-800"
                      htmlFor="review-focus"
                    >
                      Review focus{" "}
                      <span className="font-normal text-slate-500">
                        (optional)
                      </span>
                    </label>
                    <textarea
                      id="review-focus"
                      value={focus}
                      onChange={(event) => {
                        resetReview();
                        setFocus(event.target.value);
                      }}
                      rows={3}
                      placeholder="For example: focus on authorization changes or data migrations."
                      className="mt-2 w-full resize-y rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100"
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      disabled={
                        !selectedRepository ||
                        !selectedPullRequest ||
                        isLoadingPullRequestDetails ||
                        isReviewing
                      }
                      onClick={() => void submitReview()}
                      className="inline-flex h-11 items-center justify-center rounded-lg bg-violet-700 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-800 focus:outline-none focus:ring-4 focus:ring-violet-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isReviewing
                        ? "Reviewing…"
                        : reviewResult
                          ? "Retry PR review"
                          : "Submit PR review"}
                    </button>
                    {isReviewing && (
                      <span role="status" className="text-sm text-slate-600">
                        {reviewProgress || "Reviewing pull request…"}
                      </span>
                    )}
                  </div>

                  {reviewError && (
                    <div
                      role="alert"
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                    >
                      {reviewError}
                    </div>
                  )}
                </div>
              </section>

              {reviewResult && (
                <section
                  aria-labelledby="review-result-heading"
                  aria-live="polite"
                  className="mt-8"
                >
                  <header
                    className={`rounded-2xl border p-5 shadow-sm sm:p-7 ${
                      reviewPassed
                        ? "border-emerald-200 bg-emerald-50"
                        : "border-amber-200 bg-amber-50"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p
                          className={`text-xs font-bold uppercase tracking-[0.16em] ${
                            reviewPassed ? "text-emerald-800" : "text-amber-800"
                          }`}
                        >
                          {reviewPassed
                            ? "CodeForge review passed"
                            : "Review findings"}
                        </p>
                        <h2
                          id="review-result-heading"
                          className="mt-2 text-2xl font-semibold tracking-tight text-slate-950"
                        >
                          {reviewPassed
                            ? "No findings — this PR passed review"
                            : `${reviewResult.findings.length} finding${
                                reviewResult.findings.length === 1 ? "" : "s"
                              } to review`}
                        </h2>
                      </div>
                      {reviewPassed && (
                        <span className="rounded-full border border-emerald-300 bg-white px-3 py-1.5 text-sm font-bold text-emerald-800">
                          Approved by CodeForge
                        </span>
                      )}
                    </div>
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                      {reviewResult.summary}
                    </p>
                    {Object.keys(severityCounts ?? {}).length > 0 && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {(["P0", "P1", "P2", "P3"] as const).map((severity) =>
                          severityCounts?.[severity] ? (
                            <span
                              key={severity}
                              className={`rounded-full border px-3 py-1 text-xs font-bold ${severityStyles[severity]}`}
                            >
                              {severity}: {severityCounts[severity]}
                            </span>
                          ) : null,
                        )}
                      </div>
                    )}
                    {reviewPassed && (
                      <p className="mt-3 text-xs text-emerald-800">
                        This is a CodeForge assessment only; no approval or
                        review comment was submitted to GitHub.
                      </p>
                    )}
                  </header>

                  {reviewResult.findings.length > 0 && (
                    <div className="mt-5 space-y-5">
                      {reviewResult.findings.map((finding, index) => (
                        <FindingCard
                          key={`${finding.severity}-${index}`}
                          finding={finding}
                          index={index}
                          copied={copiedFinding === index}
                          onCopy={() => void copySuggestedCode(finding, index)}
                        />
                      ))}
                    </div>
                  )}
                </section>
              )}
              {isReviewing && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
                  <section
                    aria-labelledby="pr-review-progress-title"
                    aria-modal="true"
                    className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl"
                    role="dialog"
                  >
                    <div className="flex items-start gap-4">
                      <span
                        aria-hidden="true"
                        className="mt-1 h-6 w-6 shrink-0 animate-spin rounded-full border-2 border-violet-700 border-t-transparent"
                      />
                      <div>
                        <h2
                          className="text-xl font-semibold text-slate-900"
                          id="pr-review-progress-title"
                        >
                          Reviewing pull request
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                          {selectedPullRequest
                            ? `Reviewing #${selectedPullRequest.pull_request_number}: ${selectedPullRequest.title}`
                            : "The agent is working through the review tasks."}{" "}
                          This activity list updates as it makes progress.
                        </p>
                      </div>
                    </div>
                    {todos.length > 0 && (
                      <p className="mt-5 text-sm font-medium text-slate-600">
                        {todos.filter((todo) => todo.completed).length} of{" "}
                        {todos.length} tasks complete
                      </p>
                    )}
                    <ul
                      ref={todoListRef}
                      aria-live="polite"
                      className="mt-3 max-h-72 space-y-2 overflow-y-auto"
                    >
                      {todos.length > 0 ? (
                        todos.map((todo) => (
                          <li
                            ref={
                              todo.order === lastCompletedTodoOrder
                                ? lastCompletedTodoRef
                                : undefined
                            }
                            className="flex items-start gap-3 rounded-lg bg-slate-50 px-3 py-2.5"
                            key={todo.order}
                          >
                            <span
                              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                                todo.completed
                                  ? "bg-emerald-100 text-emerald-700"
                                  : "bg-slate-200 text-slate-600"
                              }`}
                            >
                              {todo.completed ? "✓" : todo.order}
                            </span>
                            <span
                              className={`text-sm leading-6 ${
                                todo.completed
                                  ? "text-slate-500 line-through"
                                  : "font-medium text-slate-800"
                              }`}
                            >
                              {todo.description}
                            </span>
                          </li>
                        ))
                      ) : (
                        <li className="rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">
                          Waiting for the agent&apos;s first progress update...
                        </li>
                      )}
                    </ul>
                  </section>
                </div>
              )}
            </section>
          </Show>
          <Show when="signed-out">
            <RedirectToSignIn />
          </Show>
        </>
      )}
    </main>
  );
}

function FindingCard({
  finding,
  index,
  copied,
  onCopy,
}: {
  finding: PRReviewFinding;
  index: number;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 px-5 py-4 sm:px-6">
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-bold ${severityStyles[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <h3 className="text-base font-semibold text-slate-900">
          Finding {index + 1}
        </h3>
      </header>
      <div className="px-5 py-5 sm:px-6">
        <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
          {finding.comment}
        </p>
        <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">
                Suggested code change
              </p>
              <p className="mt-1 break-all text-xs text-slate-600">
                <span className="font-semibold">File: </span>
                <code className="font-mono text-indigo-700">
                  {finding.file_path}
                </code>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Read-only diff. Copy the replacement if you want to apply it.
              </p>
            </div>
            <button
              type="button"
              onClick={onCopy}
              className="inline-flex h-9 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-indigo-200"
            >
              {copied ? "Copied" : "Copy suggested code"}
            </button>
          </div>
          <div className="h-[min(60vh,24rem)] min-h-56 bg-slate-950 p-1">
            <DiffEditor
              height="100%"
              original={finding.code}
              modified={finding.new_code}
              language="plaintext"
              theme="vs-dark"
              options={{
                readOnly: true,
                originalEditable: false,
                renderSideBySide: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                wordWrap: "on",
                automaticLayout: true,
              }}
            />
          </div>
        </div>
        {finding.tests && (
          <details className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <summary className="cursor-pointer text-sm font-semibold text-slate-700">
              Suggested regression test
            </summary>
            <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
              {finding.tests}
            </pre>
          </details>
        )}
      </div>
    </article>
  );
}
