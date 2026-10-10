"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchConversationalSearch,
  type ConstraintField,
  type ConversationalSearchResponse,
  type HybridSearchResult,
} from "@/lib/api";
import { formatInr, swatchForColor } from "@/lib/color-swatch";
import { restoreSnapshot, saveSnapshot, type ConversationMessage } from "@/lib/search-session";

type ViewState = {
  status: "idle" | "loading" | "error" | "ready";
  data: ConversationalSearchResponse | null;
  error: string | null;
  messages: ConversationMessage[];
};

const initialState: ViewState = { status: "idle", data: null, error: null, messages: [] };

function ProductCard({ result }: { result: HybridSearchResult }) {
  return (
    <Link
      href={result.product_url}
      aria-label={`View ${result.title}`}
      className="group overflow-hidden rounded-2xl border border-stone-200/80 bg-white transition duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-700"
    >
      <div className="product-art relative flex aspect-[4/4.6] items-end overflow-hidden p-4" style={{ "--fabric": swatchForColor(result.color) } as React.CSSProperties}>
        <div className="garment-shape" aria-hidden="true" />
        <span className="relative z-10 rounded-full bg-white/90 px-3 py-1 text-[10px] font-medium uppercase tracking-[0.16em] text-stone-700">{result.category}</span>
        <span className="absolute right-3 top-3 rounded-full bg-white/85 px-2.5 py-1 text-[10px] uppercase tracking-widest text-stone-600">Vastra Edit</span>
      </div>
      <div className="p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-stone-500">VastraAI selection</p>
        <h2 className="mt-1.5 line-clamp-2 min-h-10 text-sm font-medium leading-5 text-stone-900">{result.title}</h2>
        <p className="mt-2 text-base font-semibold text-stone-900">{formatInr(result.price_inr)}</p>
        <p className="mt-3 line-clamp-2 border-t border-stone-100 pt-3 text-xs leading-5 text-stone-600">{result.match_reason}</p>
      </div>
    </Link>
  );
}

function SearchMark() {
  return <span aria-hidden="true" className="grid size-9 place-items-center rounded-full bg-stone-900 text-sm font-semibold text-white">V</span>;
}

function filterSummary(data: ConversationalSearchResponse): string {
  const category = data.active_filters.find((filter) => filter.key === "category")?.value;
  const color = data.active_filters.find((filter) => filter.key === "color")?.value;
  const occasion = data.active_filters.find((filter) => filter.key === "occasion")?.value;
  const price = data.active_filters.find((filter) => filter.key === "price_max")?.value;
  const parts = [color, category, occasion ? `for ${occasion.toLowerCase()}` : null, price ? `under ${price.replace(/^Under\s+/i, "")}` : null].filter(Boolean);
  return parts.length ? parts.join(" ") : data.state.current_query;
}

export function SearchView() {
  const [draft, setDraft] = useState("");
  const [view, setView] = useState<ViewState>(initialState);
  const [hydrated, setHydrated] = useState(false);
  const [conversationOpen, setConversationOpen] = useState(false);
  const [colorChoicesOpen, setColorChoicesOpen] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const shouldFollowRef = useRef(true);
  const inFlightRef = useRef(false);

  useEffect(() => {
    const saved = restoreSnapshot(window.sessionStorage);
    const frame = window.requestAnimationFrame(() => {
      if (saved) setView({ status: "ready", data: saved.data, messages: saved.messages, error: null });
      setHydrated(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try { saveSnapshot(window.sessionStorage, view.data, view.messages); } catch { /* storage may be unavailable */ }
  }, [view.data, view.messages, hydrated]);

  useEffect(() => {
    const container = transcriptRef.current;
    if (container && shouldFollowRef.current) container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [view.messages, view.status]);

  const execute = useCallback(async (text: string, directUpdate?: { field: ConstraintField; operation: "REMOVE" | "SET"; value?: string }) => {
    if (inFlightRef.current) return;
    const trimmed = text.trim();
    if (!trimmed && !directUpdate) return;
    inFlightRef.current = true;
    shouldFollowRef.current = true;
    const userMessage: ConversationMessage | null = trimmed ? { id: `${Date.now()}-${Math.random()}`, role: "user", content: trimmed } : null;
    setView((current) => ({
      ...current,
      status: "loading",
      error: null,
      messages: userMessage ? [...current.messages, userMessage] : current.messages,
    }));
    setDraft("");
    try {
      const current = view.data;
      const data = await fetchConversationalSearch(current
        ? {
            session_id: current.session_id,
            expected_revision: current.revision,
            ...(directUpdate ? { updates: [directUpdate] } : { message: trimmed }),
            limit: 12,
          }
        : { query: trimmed, limit: 12 });
      const reply = data.search_status === "off_topic"
        ? "I can help you find clothing, footwear and accessories. Tell me what you are shopping for."
        : data.total === 0
          ? "I couldn’t find an exact match for those preferences. You can remove a filter to broaden your selection."
          : "I found options that match your preferences.";
      const assistantMessage: ConversationMessage = { id: `${Date.now()}-assistant`, role: "assistant", content: reply };
      setView((previous) => ({ status: "ready", data, error: null, messages: [...previous.messages, assistantMessage] }));
      setConversationOpen(true);
    } catch (error: unknown) {
      const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Your search could not be updated.";
      // Preserve the attempted turn in the transcript while the confirmed state and products remain intact.
      setView((previous) => ({ ...previous, status: "ready", error: message }));
    } finally {
      inFlightRef.current = false;
    }
  }, [view.data]);

  function onSubmit(event: React.SyntheticEvent) {
    event.preventDefault();
    void execute(draft);
  }

  function removeFilter(field: ConstraintField) {
    void execute("", { field, operation: "REMOVE" });
  }

  function startNewSearch() {
    setDraft("");
    setColorChoicesOpen(false);
    setView(initialState);
  }

  const data = view.data;
  const busy = view.status === "loading";
  const noResults = data?.total === 0;
  const contextualSuggestions = noResults ? [
    ...data!.active_filters.filter((item) => item.key === "size" || item.key === "price_max").map((item) => ({ label: `Remove ${item.label === "Price" ? "price limit" : `${item.label} ${item.value}`}`, field: item.key })),
  ] : [];

  return (
    <div className="min-h-screen bg-[#f7f5f1] text-stone-900">
      <header className="sticky top-0 z-30 border-b border-stone-200/80 bg-[#fbfaf8]/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1440px] items-center gap-4 px-4 py-3 sm:px-7">
          <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="VastraAI home">
            <SearchMark /><span className="font-serif text-xl tracking-tight">VastraAI</span>
          </Link>
          <form onSubmit={onSubmit} className="ml-auto flex min-w-0 max-w-3xl flex-1 items-center rounded-full border border-stone-300 bg-white px-4 shadow-sm focus-within:border-stone-500 focus-within:ring-2 focus-within:ring-stone-200">
            <span aria-hidden="true" className="mr-3 text-stone-400">⌕</span>
            <input
              aria-label="Search products, styles or occasions"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }}
              placeholder="Search products, styles or occasions…"
              className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-stone-400"
            />
            <button type="submit" disabled={busy || !draft.trim()} className="ml-2 rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Search</button>
          </form>
          <Link href="/catalog" className="hidden text-sm text-stone-600 transition hover:text-stone-950 sm:block">Catalog</Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 pb-16 pt-5 sm:px-7 sm:pt-8">
        {!data ? (
          <section className="mx-auto max-w-4xl py-14 text-center sm:py-24">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">A considered way to shop</p>
            <h1 className="mx-auto mt-5 max-w-2xl font-serif text-4xl leading-tight tracking-tight sm:text-6xl">Find the pieces that feel like you.</h1>
            <p className="mx-auto mt-5 max-w-lg text-sm leading-6 text-stone-600">Describe a piece, an occasion or a feeling. VastraAI keeps your preferences together as you explore.</p>
            <div className="mx-auto mt-8 max-w-2xl rounded-[1.75rem] border border-stone-200 bg-white p-3 text-left shadow-sm">
              <form onSubmit={onSubmit}>
                <label htmlFor="first-search" className="sr-only">Describe what you are looking for</label>
                <textarea id="first-search" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }} rows={2} placeholder="A black wedding dress under ₹4,000…" className="w-full resize-none bg-transparent px-4 py-3 text-base outline-none placeholder:text-stone-400" />
                <div className="flex items-center justify-between px-2 pb-1"><span className="text-xs text-stone-400">Describe it naturally · Enter to search</span><button disabled={busy || !draft.trim()} className="rounded-full bg-stone-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">{busy ? "Finding pieces…" : "Find my look"}</button></div>
              </form>
            </div>
            <div className="mt-5 flex flex-wrap justify-center gap-2">{["Wedding guest looks", "Everyday linen", "A blue kurta"].map((example) => <button key={example} onClick={() => setDraft(example)} className="rounded-full border border-stone-300 bg-white/70 px-4 py-2 text-xs text-stone-600 transition hover:border-stone-500 hover:text-stone-900">{example}</button>)}</div>
            {view.messages.map((message) => <div key={message.id} className={`mx-auto mt-4 max-w-xl rounded-2xl px-4 py-3 text-left text-sm ${message.role === "user" ? "bg-stone-900 text-white" : "bg-white text-stone-700"}`}><span className="mr-2 text-[10px] font-semibold uppercase tracking-wider opacity-65">{message.role === "user" ? "You" : "VastraAI"}</span>{message.content}</div>)}
            {busy && <p className="mt-4 text-sm text-stone-500" role="status">Finding pieces for you…</p>}
            {view.error && <p role="alert" className="mx-auto mt-4 max-w-xl rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{view.error}</p>}
          </section>
        ) : (
          <div className="grid items-start gap-7 lg:grid-cols-[minmax(280px,350px)_minmax(0,1fr)] xl:gap-10">
            <aside className="hidden lg:sticky lg:top-[82px] lg:block">
              <ConversationPanel view={view} setDraft={setDraft} onSubmit={onSubmit} transcriptRef={transcriptRef} shouldFollowRef={shouldFollowRef} busy={busy} />
            </aside>
            <section className="min-w-0">
              <div className="mb-5 flex items-center justify-between gap-3 lg:hidden">
                <p className="font-serif text-2xl">Your edit</p>
                <button onClick={() => setConversationOpen(true)} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-medium shadow-sm">Ask VastraAI <span aria-hidden="true">↗</span></button>
              </div>
              <div className="mb-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">Your selection</p>
                <h1 className="mt-2 font-serif text-3xl capitalize tracking-tight sm:text-4xl">{filterSummary(data)}</h1>
                <p className="mt-2 text-sm text-stone-600">{noResults ? "No exact matches" : `${data.total} ${data.total === 1 ? "piece" : "pieces"}`} {busy && <span className="ml-2 inline-flex items-center gap-2 text-stone-500"><span className="size-1.5 animate-pulse rounded-full bg-stone-500" />Updating your edit</span>}</p>
              </div>
              <div className="mb-6 flex flex-wrap items-center gap-2" aria-label="Active preferences">
                {data.active_filters.map((filter) => <button key={filter.key} onClick={() => removeFilter(filter.key)} disabled={busy} aria-label={`Remove ${filter.label}: ${filter.value}`} className="rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-xs text-stone-700 transition hover:border-stone-600 disabled:opacity-50">{filter.value} <span aria-hidden="true" className="ml-1 text-stone-400">×</span></button>)}
                {data.active_filters.length === 0 && <span className="text-xs text-stone-500">No filters applied</span>}
              </div>
              {view.error && <p role="alert" className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{view.error} Your confirmed preferences and results are still here.</p>}
              {noResults ? (
                <div className="rounded-2xl border border-stone-200 bg-white p-6 sm:p-9">
                  <div className="max-w-xl"><span className="text-2xl" aria-hidden="true">⌕</span><h2 className="mt-3 font-serif text-2xl">No exact matches</h2><p className="mt-2 text-sm leading-6 text-stone-600">We couldn’t find products matching all your preferences.</p>
                    <div className="mt-5 flex flex-wrap gap-2">{data.active_filters.map((filter) => <span key={filter.key} className="rounded-full bg-stone-100 px-3 py-1.5 text-xs text-stone-700">{filter.value}</span>)}</div>
                    <div className="mt-6 flex flex-wrap gap-2">{contextualSuggestions.map((suggestion) => <button key={suggestion.field} onClick={() => removeFilter(suggestion.field)} className="rounded-full border border-stone-300 px-4 py-2 text-xs font-medium transition hover:bg-stone-50">{suggestion.label}</button>)}<button onClick={() => setColorChoicesOpen((open) => !open)} className="rounded-full border border-stone-300 px-4 py-2 text-xs font-medium transition hover:bg-stone-50">Change color</button></div>
                    {colorChoicesOpen && <div className="mt-3 flex flex-wrap gap-2" aria-label="Choose a color">{["Black", "Blue", "Green", "Red", "White"].map((color) => <button key={color} onClick={() => void execute("", { field: "color", operation: "SET", value: color.toLowerCase() })} className="rounded-full bg-stone-100 px-3 py-1.5 text-xs hover:bg-stone-200">{color}</button>)}</div>}
                  </div>
                </div>
              ) : data.results.length ? (
                <div className={`grid grid-cols-2 gap-3 transition-opacity sm:gap-5 xl:grid-cols-3 ${busy ? "opacity-65" : "opacity-100"}`} aria-busy={busy}>
                  {data.results.map((result) => <ProductCard key={result.product_id} result={result} />)}
                </div>
              ) : data.search_status === "off_topic" ? (
                <div className="rounded-2xl border border-stone-200 bg-white p-7"><h2 className="font-serif text-2xl">Let’s find something to wear</h2><p className="mt-2 text-sm text-stone-600">{data.message}</p></div>
              ) : null}
              <div className="mt-8 flex flex-wrap gap-2 border-t border-stone-200 pt-5">
                <button onClick={() => void execute("show cheaper options")} disabled={busy} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-xs text-stone-700 transition hover:border-stone-600 disabled:opacity-50">Cheaper options</button>
                <button onClick={() => setColorChoicesOpen((open) => !open)} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-xs text-stone-700 transition hover:border-stone-600">Change color</button>
                {data.active_filters.some((filter) => filter.key === "price_max") && <button onClick={() => removeFilter("price_max")} disabled={busy} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-xs text-stone-700 transition hover:border-stone-600 disabled:opacity-50">Remove price limit</button>}
                {colorChoicesOpen && <div className="flex w-full flex-wrap gap-2">{["Black", "Blue", "Green", "Red", "White"].map((color) => <button key={color} disabled={busy} onClick={() => void execute("", { field: "color", operation: "SET", value: color.toLowerCase() })} className="rounded-full bg-stone-200 px-3 py-1.5 text-xs hover:bg-stone-300">{color}</button>)}</div>}
                <button onClick={startNewSearch} className="ml-auto px-3 py-2 text-xs text-stone-500 underline underline-offset-4">Start a new search</button>
              </div>
            </section>
          </div>
        )}
      </main>

      {conversationOpen && data && <div className="fixed inset-0 z-50 flex items-end bg-stone-950/35 lg:hidden" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setConversationOpen(false); }}><section role="dialog" aria-modal="true" aria-label="VastraAI shopping conversation" className="max-h-[90dvh] w-full overflow-hidden rounded-t-[1.5rem] bg-[#fbfaf8] p-4 shadow-2xl"><div className="mx-auto mb-3 h-1 w-10 rounded-full bg-stone-300" /><div className="mb-3 flex items-center justify-between"><p className="font-serif text-xl">Shopping with VastraAI</p><button onClick={() => setConversationOpen(false)} aria-label="Close conversation" className="grid size-9 place-items-center rounded-full border border-stone-200">×</button></div><ConversationPanel view={view} setDraft={setDraft} onSubmit={onSubmit} transcriptRef={transcriptRef} shouldFollowRef={shouldFollowRef} busy={busy} compact /></section></div>}
    </div>
  );
}

function ConversationPanel({
  view, setDraft, onSubmit, transcriptRef, shouldFollowRef, busy, compact = false,
}: {
  view: ViewState;
  setDraft: (value: string) => void;
  onSubmit: (event: React.SyntheticEvent) => void;
  transcriptRef: React.RefObject<HTMLDivElement | null>;
  shouldFollowRef: React.MutableRefObject<boolean>;
  busy: boolean;
  compact?: boolean;
}) {
  const data = view.data;
  return <section className={`flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm ${compact ? "max-h-[calc(90dvh-90px)]" : "h-[min(720px,calc(100dvh-110px))]"}`}>
    <div className="border-b border-stone-100 px-5 py-4"><div className="flex items-center gap-3"><SearchMark /><div><h2 className="font-medium">Shopping Assistant</h2><p className="text-xs text-stone-500">A thoughtful edit, shaped around you</p></div></div></div>
    <div ref={transcriptRef} onScroll={(event) => { const el = event.currentTarget; shouldFollowRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 72; }} className="min-h-[170px] flex-1 space-y-5 overflow-y-auto px-4 py-5" aria-live="polite">
      {!view.messages.length && <div className="rounded-xl bg-[#f7f5f1] p-4"><p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-500">VastraAI</p><p className="mt-2 text-sm leading-6 text-stone-700">Tell me what you’re looking for. We can refine color, occasion, size and budget together.</p><div className="mt-3 flex flex-wrap gap-2">{["A wedding guest dress", "Something in blue", "Everyday essentials"].map((suggestion) => <button key={suggestion} onClick={() => setDraft(suggestion)} className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-[11px] text-stone-600 hover:border-stone-500">{suggestion}</button>)}</div></div>}
      {view.messages.map((message) => <div key={message.id} className={message.role === "user" ? "ml-6" : "mr-4"}><p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.17em] text-stone-500">{message.role === "user" ? "You" : "VastraAI"}</p><div className={`rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-tr-md bg-stone-900 text-white" : "rounded-tl-md bg-[#f5f3ef] text-stone-700"}`}>{message.content}</div></div>)}
      {busy && <div className="mr-8 rounded-2xl rounded-tl-md bg-[#f5f3ef] px-4 py-3 text-xs text-stone-500"><span className="mr-2 inline-flex gap-1" aria-hidden="true"><i className="size-1.5 animate-pulse rounded-full bg-stone-500" /><i className="size-1.5 animate-pulse rounded-full bg-stone-400 [animation-delay:120ms]" /><i className="size-1.5 animate-pulse rounded-full bg-stone-300 [animation-delay:240ms]" /></span>Updating your selection</div>}
      {view.error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800">{view.error} Your current selection is unchanged.</p>}
      {data && <p className="text-center text-[10px] text-stone-400">Your preferences are saved in this search</p>}
    </div>
    <form onSubmit={onSubmit} className="border-t border-stone-100 p-3">
      <label htmlFor={compact ? "mobile-refinement" : "desktop-refinement"} className="sr-only">Message VastraAI</label>
      <div className="rounded-2xl border border-stone-300 bg-white p-2 focus-within:border-stone-500 focus-within:ring-2 focus-within:ring-stone-100"><textarea id={compact ? "mobile-refinement" : "desktop-refinement"} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }} placeholder="Make it blue, size M…" rows={2} className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-stone-400"/><div className="flex items-center justify-between px-1"><span className="text-[10px] text-stone-400">Enter to send · Shift + Enter for a new line</span><button disabled={busy} className="rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Send</button></div></div>
    </form>
  </section>;
}
