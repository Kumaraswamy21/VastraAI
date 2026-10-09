"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ApiError,
  fetchConversationalSearch,
  type ConstraintField,
  type ConversationalSearchResponse,
  type HybridSearchResult,
} from "@/lib/api";
import { formatInr, swatchForColor } from "@/lib/color-swatch";
import { restoreSearch, saveSearch } from "@/lib/search-session";

type SearchState = {
  status: "idle" | "loading" | "error" | "ready";
  data: ConversationalSearchResponse | null;
  error: string | null;
};

function SearchResultCard({ result }: { result: HybridSearchResult }) {
  return (
    <Link
      href={result.product_url}
      aria-label={`View ${result.title}`}
      className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm transition hover:border-zinc-300 hover:shadow"
    >
      <div
        className="flex h-36 items-end p-3"
        style={{ backgroundColor: swatchForColor(result.color) }}
      >
        <span className="rounded bg-white/90 px-2 py-0.5 text-xs font-medium text-zinc-800">
          {result.category}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <h2 className="line-clamp-2 text-sm font-semibold text-zinc-900">{result.title}</h2>
        <p className="text-xs capitalize text-zinc-500">{result.color}</p>
        <p className="text-xs text-zinc-600 line-clamp-2">{result.match_reason}</p>
        <p className="mt-auto pt-2 text-sm font-medium text-zinc-900">
          {formatInr(result.price_inr)}
        </p>
      </div>
    </Link>
  );
}

export function SearchView() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>({
    status: "idle",
    data: null,
    error: null,
  });

  useEffect(() => {
    const restored = restoreSearch(window.sessionStorage);
    if (restored) queueMicrotask(() => setState({ status: "ready", data: restored, error: null }));
  }, []);

  useEffect(() => {
    try {
      saveSearch(window.sessionStorage, state.data);
    } catch {
      // Storage can be disabled; the current page still works without persistence.
    }
  }, [state.data]);

  function startNewSearch() {
    setQuery("");
    setState({ status: "idle", data: null, error: null });
  }

  async function onSearch(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setState((current) => ({
        ...current,
        status: "error",
        error: "Enter a shopping request to search.",
      }));
      return;
    }
    const current = state.data;
    setState((previous) => ({ ...previous, status: "loading", error: null }));
    try {
      const data = await fetchConversationalSearch(
        current
          ? {
              session_id: current.session_id,
              expected_revision: current.revision,
              message: trimmed,
              limit: 12,
            }
          : { query: trimmed, limit: 12 },
      );
      setQuery("");
      setState({ status: "ready", data, error: null });
    } catch (error: unknown) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Search failed";
      setState((previous) => ({ ...previous, status: "error", error: message }));
    }
  }

  const ready = state.data;

  async function removeFilter(field: ConstraintField) {
    if (!ready) return;
    setState((previous) => ({ ...previous, status: "loading", error: null }));
    try {
      const data = await fetchConversationalSearch({
        session_id: ready.session_id,
        expected_revision: ready.revision,
        updates: [{ field, operation: "REMOVE" }],
        limit: 12,
      });
      setState({ status: "ready", data, error: null });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Could not remove filter";
      setState((previous) => ({ ...previous, status: "error", error: message }));
    }
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <p className="text-sm font-medium tracking-wide text-zinc-500">AI Fashion Search</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-900">
          Describe the outfit. Review the links.
        </h1>
        <Link
          href="/catalog"
          className="mt-3 inline-block text-sm font-medium text-zinc-700 underline"
        >
          Browse catalog
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
        <p className="text-base leading-7 text-zinc-600">
          Describe what you want in plain language. The app extracts filters, runs hybrid
          keyword + semantic search, and returns ranked product links from this catalog.
        </p>

        <form className="flex flex-col gap-4" onSubmit={onSearch}>
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium text-zinc-700">Shopping request</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={3}
              placeholder={ready ? "Refine it: make it blue, size M, show cheaper options…" : "Show me a black dress under ₹4,000 for a wedding."}
              className="resize-none rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm focus:border-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-200"
            />
          </label>
          <button
            type="submit"
            disabled={state.status === "loading"}
            className="w-fit rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:bg-zinc-400"
          >
            {state.status === "loading" ? "Searching…" : "Search catalog"}
          </button>
          {state.data && (
            <button type="button" onClick={startNewSearch} className="w-fit text-sm text-zinc-600 underline">
              Start new search
            </button>
          )}
        </form>

        {state.error && (
          <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {state.error}
          </p>
        )}

        {ready && (
          <section
            className={`flex flex-col gap-4 transition-opacity ${state.status === "loading" ? "opacity-60" : "opacity-100"}`}
            aria-busy={state.status === "loading"}
          >
            <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">
              <p>
                <span className="font-medium text-zinc-900">Active filters:</span>
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {ready.active_filters.length === 0 && <span className="text-zinc-500">None</span>}
                {ready.active_filters.map((filter) => (
                  <button
                    key={filter.key}
                    type="button"
                    onClick={() => removeFilter(filter.key)}
                    disabled={state.status === "loading"}
                    className="rounded-full border border-zinc-300 bg-zinc-50 px-3 py-1 text-xs text-zinc-800 hover:bg-zinc-100 disabled:cursor-wait"
                    aria-label={`Remove ${filter.label}: ${filter.value}`}
                  >
                    {filter.label}: {filter.value} <span aria-hidden="true">×</span>
                  </button>
                ))}
              </div>
              <p className="mt-1">
                <span className="font-medium text-zinc-900">Mode:</span> {ready.search_mode}
                {ready.embedding_index_status !== "ready" && (
                  <span className="text-zinc-500">
                    {" "}
                    (embeddings: {ready.embedding_index_status})
                  </span>
                )}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                Revision {ready.revision} · {ready.interpreted_as.replace("_", " ")}
              </p>
              {ready.message && <p className="mt-2 text-zinc-600">{ready.message}</p>}
              {ready.suggestions.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-zinc-600">
                  {ready.suggestions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>

            <p className="text-sm text-zinc-600">
              {ready.total === 0
                ? "No matching products for this query."
                : `${ready.total} result${ready.total === 1 ? "" : "s"}`}
            </p>

            {ready.results.length > 0 && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {ready.results.map((result) => (
                  <SearchResultCard key={result.product_id} result={result} />
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
