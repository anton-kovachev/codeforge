"use client";

import { useState, useEffect, useRef } from "react";
import { RedirectToSignIn, Show, useAuth } from "@clerk/react";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { Editor, DiffEditor } from "@monaco-editor/react";
import type { TodoItem } from "./models";
import {
  isDebuggedCodeResult,
  isRecord,
  isTodoItem,
  languageOptions,
  type LanguageOption,
} from "./utils";

const SAMPLE_CODE =
  "# Write your Python code here\n def divide(a: float, b: float) -> float:\n    return a % b";

export default function Workspace() {
  const [code, setCode] = useState(SAMPLE_CODE);
  const [language, setLanguage] = useState<LanguageOption>(languageOptions[0]);
  const [updatedCode, setUpdatedCode] = useState("");
  const [tests, setTests] = useState("# Optional test code here");
  const [updatedTests, setUpdatedTests] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [testInstructions, setTestInstructions] = useState("");
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const todoListRef = useRef<HTMLUListElement>(null);
  const lastCompletedTodoRef = useRef<HTMLLIElement>(null);
  const handleCodeReviewRef = useRef<(() => Promise<void>) | null>(null);
  const reviewInProgressRef = useRef(false);
  const lastCompletedTodoOrder = todos.reduce<number | undefined>(
    (lastCompletedOrder, todo) =>
      todo.completed ? todo.order : lastCompletedOrder,
    undefined,
  );

  const sessionId = null;

  const { getToken, isLoaded } = useAuth();
  const baseApiUrl = `${process.env.NEXT_PUBLIC_CODEFORGE_API_BASE_URL?.replace(/\/+$/, "")}/api`;
  console.log("Base API URL:", baseApiUrl);

  useEffect(() => {
    if (language.value === "python") {
      setCode(SAMPLE_CODE);
    } else {
      setCode(`# Write your ${language.label} code here`);
    }
    setTests(`# Optional test code for ${language.label} here`);
  }, [language]);

  useEffect(() => {
    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key !== "F5" && event.key !== "F7") {
        return;
      }

      event.stopImmediatePropagation();
      event.preventDefault();

      if (event.key === "F5" && code) handleCodeReview();
      if (event.key === "F7" && tests) handleCodeReview();
    };

    window.addEventListener("keyup", handleKeyUp);
    return () => window.removeEventListener("keyup", handleKeyUp);
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

  async function handleCodeReview() {
    if (reviewInProgressRef.current) {
      return;
    }

    reviewInProgressRef.current = true;
    setIsReviewing(true);
    setTodos([]);
    setReviewError("");
    setDescription("");
    let terminalEventReceived = false;

    try {
      const debugCodeUrl = `${baseApiUrl}/debug-code`;
      const token = await getToken();
      if (!token) {
        throw new Error(
          "Your Clerk session has expired. Please sign in again.",
        );
      }
      let currentToken = token;

      await fetchEventSource(debugCodeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          code,
          language: language.value,
          tests,
          session_id: sessionId,
          instructions,
          test_instructions: testInstructions,
        }),
        fetch: async (input, init) => {
          const headers = new Headers(init?.headers);
          headers.set("Authorization", `Bearer ${currentToken}`);
          let response = await fetch(input, { ...init, headers });
          if (response.status === 403) {
            await response.body?.cancel();
            const refreshedToken = await getToken({ skipCache: true });
            if (!refreshedToken) {
              throw new Error(
                "Your Clerk session has expired. Please sign in again.",
              );
            }
            currentToken = refreshedToken;
            headers.set("Authorization", `Bearer ${currentToken}`);
            response = await fetch(input, { ...init, headers });
          }
          return response;
        },
        onopen: async (response) => {
          if (!response.ok) {
            throw new Error(
              `Debug request failed with status ${response.status}.`,
            );
          }
        },
        onmessage: (event) => {
          if (!event.data || terminalEventReceived) {
            return;
          }

          const parsedData: unknown = JSON.parse(event.data);
          if (event.event === "progress") {
            if (
              !isRecord(parsedData) ||
              !isRecord(parsedData.todo_report) ||
              !Array.isArray(parsedData.todo_report.todos) ||
              !parsedData.todo_report.todos.every(isTodoItem)
            ) {
              throw new Error(
                "Received an invalid progress event from the service.",
              );
            }

            setTodos(
              [...parsedData.todo_report.todos].sort(
                (first, second) => first.order - second.order,
              ),
            );
          } else if (event.event === "result") {
            if (
              !isRecord(parsedData) ||
              !isDebuggedCodeResult(parsedData.result)
            ) {
              throw new Error(
                "Received an invalid result event from the service.",
              );
            }

            const result = parsedData.result;
            setCode(result.code);
            debugger;
            setUpdatedCode(result.updated_code ?? "");
            setDescription(result.description);
            setTests(result.tests);
            setUpdatedTests(result.updated_tests ?? "");
            terminalEventReceived = true;
            setIsReviewing(false);
          } else if (event.event === "error") {
            const message =
              isRecord(parsedData) && typeof parsedData.error === "string"
                ? parsedData.error
                : "The debugging service returned an error.";
            terminalEventReceived = true;
            setReviewError(message);
            setIsReviewing(false);
          }
        },
        onclose: () => {
          debugger;
          if (!terminalEventReceived) {
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
      setReviewError(
        error instanceof Error ? error.message : "The code review failed.",
      );
    } finally {
      reviewInProgressRef.current = false;
      setIsReviewing(false);
      setTodos([]);
    }
  }

  useEffect(() => {
    handleCodeReviewRef.current = handleCodeReview;
  });

  function handleAcceptCode() {
    if (updatedCode) {
      setCode(updatedCode);
    }
    setUpdatedCode("");
    setDescription("");
  }

  function handleDeclineCode() {
    setUpdatedCode("");
    setDescription("");
  }

  function handleAcceptTests() {
    if (updatedTests) {
      setTests(updatedTests);
    }
    setUpdatedTests("");
    setDescription("");
  }

  function handleDeclineTests() {
    setUpdatedTests("");
    setDescription("");
  }

  return (
    <main className="flex-1 bg-[#f7f8fc] text-slate-950">
      {isLoaded ? (
        <>
          <Show when="signed-in">
            <section className="mx-auto w-full max-w-8xl px-5 py-10 sm:px-8 sm:py-12 lg:px-12">
              <div className="mb-8 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
                <div className="max-w-2xl">
                  <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3.5 py-1.5 text-sm font-medium text-indigo-700 shadow-sm">
                    <span className="h-2 w-2 rounded-full bg-indigo-500" />
                    CodeForge workspace
                  </div>
                  <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
                    Debug your code with confidence.
                  </h1>
                  <p className="mt-3 text-base leading-7 text-slate-600">
                    Share your code and context. CodeForge will run it, review
                    the results, and suggest a fix.
                  </p>
                </div>
              </div>

              {description && (updatedCode || updatedTests) && (
                <aside
                  aria-label="Summary of suggested changes"
                  className="relative mb-6 rounded-2xl border border-indigo-200 bg-indigo-50 p-5 pr-14 shadow-sm sm:p-6 sm:pr-16"
                  role="status"
                >
                  <h2 className="text-lg font-semibold text-slate-900">
                    What changed and why
                  </h2>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                    {description}
                  </p>
                  <button
                    aria-label="Close change summary"
                    className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-indigo-100 hover:text-slate-900 focus:outline-none focus:ring-4 focus:ring-indigo-300/40"
                    onClick={() => setDescription("")}
                    type="button"
                  >
                    <span aria-hidden="true" className="text-2xl leading-none">
                      ×
                    </span>
                  </button>
                </aside>
              )}

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-x-6 lg:gap-y-0 lg:grid-rows-[auto_auto_auto]">
                <div className="contents">
                  <section className="order-1 flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-indigo-950/5 lg:col-start-1 lg:row-start-1 lg:mb-8">
                    <div className="flex h-24 items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-6">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">
                          Code
                        </p>
                        <h2 className="mt-1 text-lg font-semibold text-slate-900">
                          {updatedCode
                            ? "Review the changes"
                            : "Your source code"}
                        </h2>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {updatedCode && (
                          <>
                            <button
                              type="button"
                              onClick={handleAcceptCode}
                              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg bg-green-600 px-3 text-sm font-semibold text-white transition hover:bg-green-700 focus:outline-none focus:ring-4 focus:ring-green-300/40"
                            >
                              Accept
                            </button>
                            <button
                              type="button"
                              onClick={handleDeclineCode}
                              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg bg-red-500 px-3 text-sm font-semibold text-black transition hover:bg-red-600 focus:outline-none focus:ring-4 focus:ring-red-300/40"
                            >
                              Decline
                            </button>
                          </>
                        )}
                        <label className="flex items-center gap-2 text-sm font-medium text-slate-600">
                          <span>Language</span>
                          <select
                            value={language.value}
                            onChange={(event) => {
                              const selectedLanguage = languageOptions.find(
                                (option) => option.value === event.target.value,
                              );
                              if (selectedLanguage) {
                                setLanguage(selectedLanguage);
                              }
                            }}
                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                          >
                            {languageOptions.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          disabled={!code || isReviewing}
                          type="button"
                          onClick={handleCodeReview}
                          className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-300/40 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Debug Code
                        </button>
                      </div>
                    </div>
                    <div className="flex-1 bg-slate-950 p-2">
                      <div className="h-[min(68vh,44rem)] min-h-[28rem] overflow-hidden rounded-lg">
                        {updatedCode ? (
                          <DiffEditor
                            height="100%"
                            original={code}
                            modified={updatedCode}
                            language={language.monacoLanguage}
                            theme="vs-dark"
                            options={{
                              readOnly: true,
                              renderSideBySide: true,
                              minimap: { enabled: false },
                              scrollBeyondLastLine: false,
                            }}
                          />
                        ) : (
                          <Editor
                            height="100%"
                            language={language.monacoLanguage}
                            value={code}
                            onChange={(value) => setCode(value ?? "")}
                            theme="vs-dark"
                            options={{
                              minimap: { enabled: false },
                              scrollBeyondLastLine: false,
                            }}
                          />
                        )}
                      </div>
                    </div>
                    <p className="flex min-h-[52px] items-center border-t border-slate-100 px-5 py-3 text-sm text-slate-500 sm:px-6">
                      {updatedCode
                        ? "Compare the original and updated code side by side."
                        : "Edit the starter code or paste in the code you want reviewed."}
                    </p>
                  </section>
                  <section className="order-3 rounded-2xl border border-slate-200 bg-white p-5 mt-5 gap-4 shadow-sm shadow-indigo-950/5 sm:p-6 lg:col-start-1 lg:row-start-2 lg:mb-6">
                    <label
                      htmlFor="instructions"
                      className="block text-lg font-semibold text-slate-900"
                    >
                      Instructions
                      <span className="ml-2 align-middle text-xs font-medium text-slate-400">
                        Optional
                      </span>
                    </label>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      Tell CodeForge what to focus on.
                    </p>
                    <textarea
                      id="instructions"
                      value={instructions}
                      onChange={(e) => setInstructions(e.target.value)}
                      placeholder="For example: focus on edge cases and explain any behavior changes."
                      rows={4}
                      className="mt-4 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-100"
                    />
                  </section>
                  <div className="order-5 flex flex-col items-start justify-between gap-4 rounded-2xl bg-slate-950 px-5 py-5 text-white sm:flex-row sm:items-center sm:px-7 lg:col-start-1 lg:row-start-3">
                    <div>
                      <h2 className="text-lg font-semibold">
                        Ready for a review?
                      </h2>
                      <p className="mt-1 text-sm text-slate-300">
                        CodeForge will run your code, test it, and explain its
                        recommendations.
                      </p>
                    </div>
                    {code && (
                      <button
                        disabled={!code || isReviewing}
                        type="button"
                        onClick={handleCodeReview}
                        className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-5 text-sm font-semibold text-slate-950 transition hover:bg-indigo-50 focus:outline-none focus:ring-4 focus:ring-indigo-300/40 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isReviewing ? "Review in progress" : "Debug code"}
                        <span aria-hidden="true">→</span>
                      </button>
                    )}
                  </div>
                </div>

                <div className="contents">
                  <section className="order-2 flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm shadow-indigo-950/5 lg:col-start-2 lg:row-start-1 lg:mb-8">
                    <div className="flex h-24 items-center justify-between gap-4 border-b border-slate-100 px-5 py-4 sm:px-6">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-indigo-600">
                          Optional
                        </p>
                        <h2 className="mt-1 text-lg font-semibold text-slate-900">
                          {updatedTests ? "Review test changes" : "Write tests"}
                        </h2>
                      </div>
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {updatedTests && (
                          <>
                            <button
                              type="button"
                              onClick={handleAcceptTests}
                              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg bg-green-600 px-3 text-sm font-semibold text-white transition hover:bg-green-700 focus:outline-none focus:ring-4 focus:ring-green-300/40"
                            >
                              Accept
                            </button>
                            <button
                              type="button"
                              onClick={handleDeclineTests}
                              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg bg-red-500 px-3 text-sm font-semibold text-black transition hover:bg-red-600 focus:outline-none focus:ring-4 focus:ring-red-300/40"
                            >
                              Decline
                            </button>
                          </>
                        )}
                        <p className="text-right text-sm font-medium text-slate-600">
                          Language:{" "}
                          <span className="font-semibold text-slate-900">
                            {language.label}
                          </span>
                        </p>
                        <button
                          disabled={!code || isReviewing}
                          type="button"
                          onClick={handleCodeReview}
                          className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-3 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-4 focus:ring-indigo-300/40 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          Test Code
                        </button>
                      </div>
                    </div>
                    <div className="relative flex-1 bg-slate-950 p-2">
                      <div className="h-[min(68vh,44rem)] min-h-[28rem] overflow-hidden rounded-lg">
                        {updatedTests ? (
                          <DiffEditor
                            height="100%"
                            original={tests}
                            modified={updatedTests}
                            language={language.monacoLanguage}
                            theme="vs-dark"
                            options={{
                              readOnly: true,
                              renderSideBySide: true,
                              minimap: { enabled: false },
                              scrollBeyondLastLine: false,
                            }}
                          />
                        ) : (
                          <Editor
                            height="100%"
                            language={language.monacoLanguage}
                            value={tests}
                            onChange={(value) => setTests(value ?? "")}
                            theme="vs-dark"
                            options={{
                              minimap: { enabled: false },
                              scrollBeyondLastLine: false,
                            }}
                          />
                        )}
                      </div>
                    </div>
                    <p className="flex min-h-[52px] items-center border-t border-slate-100 px-5 py-3 text-sm text-slate-500 sm:px-6">
                      {updatedTests
                        ? "Compare the original and updated tests side by side."
                        : "Add tests for your code, or leave this blank and CodeForge can write them."}
                    </p>
                  </section>

                  <section className="order-4 rounded-2xl mt-5 gap-4 border border-slate-200 bg-white p-5 shadow-sm shadow-indigo-950/5 sm:p-6 lg:col-start-2 lg:row-start-2 lg:mb-6">
                    <label
                      htmlFor="test-instructions"
                      className="block text-lg font-semibold text-slate-900"
                    >
                      Test instructions
                      <span className="ml-2 align-middle text-xs font-medium text-slate-400">
                        Optional
                      </span>
                    </label>
                    <p className="mt-1 text-sm leading-6 text-slate-600">
                      Add guidance for writing or running the tests.
                    </p>
                    <textarea
                      id="test-instructions"
                      value={testInstructions}
                      onChange={(event) =>
                        setTestInstructions(event.target.value)
                      }
                      placeholder="For example: include edge cases for empty input."
                      rows={4}
                      className="mt-4 w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-100"
                    />
                  </section>

                  <div className="order-6 flex flex-col items-start justify-between gap-4 rounded-2xl bg-slate-950 px-5 py-5 text-white sm:flex-row sm:items-center sm:px-7 lg:col-start-2 lg:row-start-3">
                    <div>
                      <h2 className="text-lg font-semibold">Ready to test?</h2>
                      <p className="mt-1 text-sm text-slate-300">
                        CodeForge will test your code, fix it and enhance the
                        tests
                      </p>
                    </div>
                    {code && (
                      <button
                        disabled={!code || isReviewing}
                        type="button"
                        onClick={handleCodeReview}
                        className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-5 text-sm font-semibold text-slate-950 transition hover:bg-indigo-50 focus:outline-none focus:ring-4 focus:ring-indigo-300/40 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isReviewing ? "Testing..." : "Test Code"}
                        <span aria-hidden="true">→</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {reviewError && (
                <p
                  className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                  role="alert"
                >
                  {reviewError}
                </p>
              )}
              {isReviewing && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
                  <section
                    aria-labelledby="review-progress-title"
                    aria-modal="true"
                    className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl"
                    role="dialog"
                  >
                    <div className="flex items-start gap-4">
                      <span
                        aria-hidden="true"
                        className="mt-1 h-6 w-6 shrink-0 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent"
                      />
                      <div>
                        <h2
                          className="text-xl font-semibold text-slate-900"
                          id="review-progress-title"
                        >
                          Reviewing your code
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                          The agent is working through the review tasks. This
                          activity list updates as it makes progress.
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
              {reviewError && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
                  <section
                    aria-labelledby="review-error-title"
                    aria-modal="true"
                    className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl"
                    role="dialog"
                  >
                    <div className="flex items-start gap-4">
                      <div>
                        <h2
                          className="text-xl font-semibold text-slate-900 text-red-600"
                          id="review-error-title"
                        >
                          An error occurred
                        </h2>
                        <p className="mt-1 text-sm leading-6 text-slate-600">
                          {reviewError}
                        </p>
                      </div>
                      <button
                        onClick={() => setReviewError(null)}
                        className="ml-auto rounded bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
                      >
                        Ok
                      </button>
                    </div>
                  </section>
                </div>
              )}
            </section>
          </Show>
          <Show when="signed-out">
            <RedirectToSignIn />
          </Show>
        </>
      ) : (
        <div className="mx-auto max-w-8xl px-6 py-16 text-sm font-medium text-slate-500 sm:px-10">
          Loading your workspace...
        </div>
      )}
    </main>
  );
}
