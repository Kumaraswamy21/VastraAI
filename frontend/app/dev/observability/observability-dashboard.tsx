"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError, fetchObservability, type ObservabilitySummary,
  type ProviderMetric, type RecentProviderEvent,
} from "@/lib/api";

type SearchData = {
  stages: Record<string, number | null>;
  modes: { search_mode: string; count: number }[];
  recent: { timestamp: string; request_id: string; search_mode: string; outcome: string; total_latency_ms: number; final_result_count: number; fallback_used: boolean }[];
};
type ProviderData = { breakdown: ProviderMetric[]; recent: RecentProviderEvent[] };
type Detail = { search: Record<string, unknown> | null; provider_events: Record<string, unknown>[] };

const fmt = (value: number | null | undefined, suffix = "") =>
  value == null ? "Unavailable" : `${value.toFixed(1)}${suffix}`;

export function ObservabilityDashboard() {
  const [range, setRange] = useState("24h");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [operation, setOperation] = useState("");
  const [outcome, setOutcome] = useState("");
  const [mode, setMode] = useState("");
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [providers, setProviders] = useState<ProviderData | null>(null);
  const [search, setSearch] = useState<SearchData | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [summaryData, providerData, searchData] = await Promise.all([
        fetchObservability<ObservabilitySummary>("summary", { range }),
        fetchObservability<ProviderData>("providers", { range, provider, model, operation, outcome }),
        fetchObservability<SearchData>("search", { range, search_mode: mode }),
      ]);
      setError("");
      setSummary(summaryData); setProviders(providerData); setSearch(searchData);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not load observability data");
    }
  }, [range, provider, model, operation, outcome, mode]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function inspect(requestId: string) {
    try { setDetail(await fetchObservability<Detail>(`requests/${requestId}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Request lookup failed"); }
  }

  const cards = summary ? [
    ["AI requests", summary.ai_requests],
    ["Search requests", summary.search_requests],
    ["AI success", summary.ai_requests ? `${(summary.ai_successes / summary.ai_requests * 100).toFixed(1)}%` : "Unavailable"],
    ["Avg search latency", fmt(summary.search_avg_latency_ms, " ms")],
    ["Estimated API cost", summary.estimated_api_cost == null ? "Unavailable" : `$${summary.estimated_api_cost.toFixed(6)}`],
    ["Fallbacks", summary.fallback_count],
  ] : [];

  const stages = ["constraint_parsing_ms", "query_embedding_ms", "semantic_search_ms", "keyword_search_ms", "fusion_ms", "explanation_ms"];
  return (
    <main className="min-h-screen bg-zinc-50 p-6 text-zinc-900">
      <div className="mx-auto max-w-7xl space-y-8">
        <header><p className="text-sm text-zinc-500">Developer tools</p><h1 className="text-3xl font-semibold">AI & search observability</h1></header>
        <section className="flex flex-wrap gap-3 rounded-xl border bg-white p-4">
          <select value={range} onChange={(e) => setRange(e.target.value)} className="rounded border p-2"><option value="1h">Last hour</option><option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option></select>
          <input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="Provider" className="rounded border p-2" />
          <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="Model" className="rounded border p-2" />
          <input value={operation} onChange={(e) => setOperation(e.target.value)} placeholder="Operation" className="rounded border p-2" />
          <input value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="Outcome" className="rounded border p-2" />
          <input value={mode} onChange={(e) => setMode(e.target.value)} placeholder="Search mode" className="rounded border p-2" />
        </section>
        {error && <p className="rounded border border-red-200 bg-red-50 p-3 text-red-800">{error}</p>}
        <section><h2 className="mb-3 text-xl font-semibold">Overview</h2><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">{cards.map(([label, value]) => <div key={String(label)} className="rounded-xl border bg-white p-4"><p className="text-xs text-zinc-500">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>)}</div></section>
        <section><h2 className="mb-3 text-xl font-semibold">Provider usage</h2><div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-zinc-100"><tr>{["Provider / model", "Operation", "Requests", "Success", "Average", "P95", "Tokens", "Estimated cost"].map(x => <th key={x} className="p-3">{x}</th>)}</tr></thead><tbody>{providers?.breakdown.map(row => <tr key={`${row.provider}-${row.model}-${row.operation}`} className="border-t"><td className="p-3">{row.provider}<br/><span className="text-xs text-zinc-500">{row.model}</span></td><td className="p-3">{row.operation}</td><td className="p-3">{row.requests}</td><td className="p-3">{row.requests ? `${(row.successes / row.requests * 100).toFixed(1)}%` : "—"}</td><td className="p-3">{fmt(row.avg_latency_ms, " ms")}</td><td className="p-3">{fmt(row.p95_latency_ms, " ms")}</td><td className="p-3">{row.total_tokens ?? "Unavailable"}</td><td className="p-3">{row.estimated_api_cost == null ? "Unavailable" : `$${row.estimated_api_cost}`}</td></tr>)}</tbody></table></div></section>
        <section><h2 className="mb-3 text-xl font-semibold">Search performance</h2><div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-zinc-100"><tr><th className="p-3">Stage</th><th>Average</th><th>P50</th><th>P95</th></tr></thead><tbody>{stages.map(stage => <tr key={stage} className="border-t"><td className="p-3">{stage.replaceAll("_", " ")}</td><td>{fmt(search?.stages[`${stage}_avg`], " ms")}</td><td>{fmt(search?.stages[`${stage}_p50`], " ms")}</td><td>{fmt(search?.stages[`${stage}_p95`], " ms")}</td></tr>)}</tbody></table></div></section>
        <section><h2 className="mb-3 text-xl font-semibold">Search modes</h2><div className="flex flex-wrap gap-3">{search?.modes.map(row => <div key={row.search_mode} className="rounded-xl border bg-white p-4"><span className="font-medium">{row.search_mode}</span> · {row.count}</div>)}</div></section>
        <section><h2 className="mb-3 text-xl font-semibold">Recent provider requests</h2><div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-zinc-100"><tr><th className="p-3">Time</th><th>Request</th><th>Provider / model</th><th>Operation</th><th>Latency</th><th>Outcome</th></tr></thead><tbody>{providers?.recent.map((row, index) => <tr key={`${row.request_id}-${index}`} className="border-t"><td className="p-3">{new Date(row.timestamp).toLocaleString()}</td><td><button className="underline" onClick={() => inspect(row.search_request_id ?? row.request_id)}>{(row.search_request_id ?? row.request_id).slice(0, 8)}</button></td><td>{row.provider} / {row.model}</td><td>{row.operation}</td><td>{fmt(row.latency_ms, " ms")}</td><td>{row.outcome}</td></tr>)}</tbody></table></div></section>
        {detail && <section className="rounded-xl border bg-white p-4"><h2 className="text-xl font-semibold">Request detail</h2><pre className="mt-3 overflow-x-auto rounded bg-zinc-950 p-4 text-xs text-zinc-100">{JSON.stringify(detail, null, 2)}</pre></section>}
      </div>
    </main>
  );
}
