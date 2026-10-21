import Link from "next/link";

const features = [
  {
    number: "01",
    title: "Build with a copilot",
    description:
      "Turn your ideas into working code with an AI partner that helps you move from first draft to finished feature.",
  },
  {
    number: "02",
    title: "Debug with context",
    description:
      "Untangle errors faster. Get clear explanations, practical fixes, and a better sense of what went wrong.",
  },
  {
    number: "03",
    title: "Stay in your flow",
    description:
      "Ask questions, explore solutions, and keep making progress without losing sight of the problem you’re solving.",
  },
];

export default function Home() {
  return (
    <main className="flex-1 bg-[#f7f8fc] text-slate-950">
      <section className="mx-auto grid w-full max-w-7xl items-center gap-14 px-6 pb-20 pt-16 sm:px-10 sm:pt-24 lg:grid-cols-[1fr_0.92fr] lg:gap-16 lg:px-12 lg:pb-28">
        <div className="max-w-2xl">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white px-3.5 py-1.5 text-sm font-medium text-indigo-700 shadow-sm">
            <span className="h-2 w-2 rounded-full bg-indigo-500" />
            Your AI partner for better builds
          </div>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-tight sm:text-6xl lg:text-7xl">
            Make space for
            <span className="block bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">
              your next big idea.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-slate-600 sm:text-xl">
            CodeForge helps you write, understand, and debug code with AI.
            Spend less time stuck on errors and more time bringing good ideas to
            life.
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/workspace"
              className="inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-6 text-sm font-semibold text-white shadow-lg shadow-indigo-600/20 transition hover:bg-indigo-700"
            >
              Start building
              <span aria-hidden="true">→</span>
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex h-12 items-center justify-center rounded-lg border border-slate-200 bg-white px-6 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              Explore CodeForge
            </a>
          </div>
          <p className="mt-4 text-sm text-slate-500">
            A clearer path from question to working code.
          </p>
        </div>

        <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:justify-self-end">
          <div className="absolute -inset-5 rounded-[2rem] bg-gradient-to-br from-indigo-200/70 via-violet-100/50 to-sky-100/80 blur-2xl" />
          <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-indigo-950/10">
            <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-5 py-4">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </div>
              <span className="font-mono text-xs text-slate-400">
                debug-session.ts
              </span>
              <span className="w-10" />
            </div>
            <div className="bg-slate-950 px-5 py-7 font-mono text-sm leading-7 sm:px-7">
              <p className="text-slate-500">
                <span className="mr-5 text-slate-700">1</span>
                <span className="text-violet-300">function</span>{" "}
                <span className="text-sky-300">getTotal</span>
                <span className="text-slate-300">(items) {"{"}</span>
              </p>
              <p className="text-slate-500">
                <span className="mr-5 text-slate-700">2</span>
                <span className="ml-5 text-violet-300">return</span>{" "}
                <span className="text-sky-200">items.reduce</span>
                <span className="text-slate-300">(</span>
              </p>
              <p className="text-slate-500">
                <span className="mr-5 text-slate-700">3</span>
                <span className="ml-10 text-slate-300">
                  (total, item) =&gt; total + item.price,
                </span>
              </p>
              <p className="rounded bg-rose-400/10 text-slate-500">
                <span className="mr-5 text-rose-400">4</span>
                <span className="text-rose-300">);</span>
                <span className="ml-2 text-xs text-rose-300">
                  Empty list can throw
                </span>
              </p>
              <p className="text-slate-500">
                <span className="mr-5 text-slate-700">5</span>
                <span className="text-slate-300">{"}"}</span>
              </p>
            </div>
            <div className="border-t border-slate-100 bg-white p-5 sm:p-6">
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    fill="none"
                    className="h-4 w-4"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.36-6.36-1.42 1.42M7.06 16.94l-1.42 1.42m12.72 0-1.42-1.42M7.06 7.06 5.64 5.64M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
                    />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    Let’s fix this together
                  </p>
                  <p className="mt-1 text-sm leading-6 text-slate-600">
                    The reducer needs an initial value. Add{" "}
                    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-indigo-700">
                      0
                    </code>{" "}
                    as the second argument to avoid an error on empty lists.
                  </p>
                </div>
              </div>
              <div className="mt-5 flex items-center justify-between rounded-lg bg-slate-50 px-3.5 py-3">
                <span className="text-xs font-medium text-slate-500">
                  AI suggestion
                </span>
                <span className="rounded-md bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700">
                  Ready to apply
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        id="how-it-works"
        className="border-t border-slate-200 bg-white px-6 py-16 sm:px-10 sm:py-20 lg:px-12"
      >
        <div className="mx-auto max-w-7xl">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.16em] text-indigo-600">
              Your workflow, upgraded
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">
              From “why isn’t this working?” to “look what I built.”
            </h2>
            <p className="mt-4 text-base leading-7 text-slate-600">
              Whether you’re starting fresh or chasing down a tricky bug,
              CodeForge is here to help you find your next step.
            </p>
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
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
          <div className="mt-10 flex flex-col items-start justify-between gap-5 rounded-2xl bg-slate-950 px-6 py-7 text-white sm:flex-row sm:items-center sm:px-8">
            <div>
              <h3 className="text-xl font-semibold">Ready to get unstuck?</h3>
              <p className="mt-1 text-sm text-slate-300">
                Bring a question, a bug, or your next big idea.
              </p>
            </div>
            <Link
              href="/workspace"
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-5 text-sm font-semibold text-slate-950 transition hover:bg-indigo-50"
            >
              Open your workspace
              <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
