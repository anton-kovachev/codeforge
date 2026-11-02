"use client";

import { useRef, useState } from "react";
import Link from "next/link";

type WorkflowStep = {
  number: string;
  title: string;
  description: string;
};

type HowItWorksTabsProps = {
  features: WorkflowStep[];
  prReviewSteps: WorkflowStep[];
};

type WorkflowTab = "debug" | "pr-review";

export default function HowItWorksTabs({
  features,
  prReviewSteps,
}: HowItWorksTabsProps) {
  const [activeTab, setActiveTab] = useState<WorkflowTab>("debug");
  const debugTabRef = useRef<HTMLButtonElement>(null);
  const prReviewTabRef = useRef<HTMLButtonElement>(null);

  function activateTab(tab: WorkflowTab) {
    setActiveTab(tab);
    if (tab === "debug") {
      debugTabRef.current?.focus();
    } else {
      prReviewTabRef.current?.focus();
    }
  }

  function handleTabKeyDown(
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentTab: WorkflowTab,
  ) {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      activateTab(currentTab === "debug" ? "pr-review" : "debug");
    } else if (event.key === "Home") {
      event.preventDefault();
      activateTab("debug");
    } else if (event.key === "End") {
      event.preventDefault();
      activateTab("pr-review");
    }
  }

  return (
    <div className="mt-10">
      <div
        role="tablist"
        aria-label="CodeForge workflows"
        className="inline-flex rounded-xl border border-slate-200 bg-slate-100 p-1"
      >
        <button
          ref={debugTabRef}
          id="how-tab-debug"
          type="button"
          role="tab"
          aria-selected={activeTab === "debug"}
          aria-controls="how-panel-debug"
          tabIndex={activeTab === "debug" ? 0 : -1}
          onClick={() => setActiveTab("debug")}
          onKeyDown={(event) => handleTabKeyDown(event, "debug")}
          className={`rounded-lg px-4 py-2.5 text-sm font-semibold transition focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-300/50 ${
            activeTab === "debug"
              ? "bg-white text-indigo-700 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Debug &amp; improve code
        </button>
        <button
          ref={prReviewTabRef}
          id="how-tab-pr-review"
          type="button"
          role="tab"
          aria-selected={activeTab === "pr-review"}
          aria-controls="how-panel-pr-review"
          tabIndex={activeTab === "pr-review" ? 0 : -1}
          onClick={() => setActiveTab("pr-review")}
          onKeyDown={(event) => handleTabKeyDown(event, "pr-review")}
          className={`rounded-lg px-4 py-2.5 text-sm font-semibold transition focus:outline-none focus-visible:ring-4 focus-visible:ring-violet-300/50 ${
            activeTab === "pr-review"
              ? "bg-white text-violet-700 shadow-sm"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Review a pull request
        </button>
      </div>

      <section
        id="how-panel-debug"
        role="tabpanel"
        aria-labelledby="how-tab-debug"
        tabIndex={0}
        hidden={activeTab !== "debug"}
        className="mt-6 focus:outline-none"
      >
        <div className="grid gap-4 md:grid-cols-3">
          {features.map((feature) => (
            <article
              key={feature.number}
              className="rounded-xl border border-slate-200 bg-[#f7f8fc] p-6"
            >
              <span className="font-mono text-sm font-semibold text-indigo-600">
                {feature.number}
              </span>
              <h3 className="mt-5 text-lg font-semibold text-slate-900">
                {feature.title}
              </h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {feature.description}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section
        id="how-panel-pr-review"
        role="tabpanel"
        aria-labelledby="how-tab-pr-review"
        tabIndex={0}
        hidden={activeTab !== "pr-review"}
        className="mt-6 focus:outline-none"
      >
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-violet-700">
              Pull request review
            </p>
            <h3 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">
              From repository search to file-specific feedback
            </h3>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Review a GitHub change with its surrounding project context, then
              use concrete findings and suggested code to decide what to
              address.
            </p>
          </div>
          <Link
            href="/pr-review"
            className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-violet-700 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-800"
          >
            Review a pull request
            <span aria-hidden="true">→</span>
          </Link>
        </div>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {prReviewSteps.map((step) => (
            <article
              key={step.number}
              className="rounded-xl border border-violet-100 bg-violet-50/60 p-5"
            >
              <span className="font-mono text-sm font-semibold text-violet-700">
                {step.number}
              </span>
              <h4 className="mt-4 text-base font-semibold text-slate-900">
                {step.title}
              </h4>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {step.description}
              </p>
            </article>
          ))}
        </div>
        <p className="mt-5 text-xs leading-5 text-slate-500">
          A CodeForge review is not a GitHub approval and does not merge a pull
          request. Any GitHub review comments are limited to confirmed findings.
        </p>
      </section>
    </div>
  );
}
