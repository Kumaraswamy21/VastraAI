"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  fetchConversationalSearch,
  fetchShopifySearch,
  type ConstraintField,
  type ConversationalSearchResponse,
  type HybridSearchResult,
  type ShopifySearchResponse,
} from "@/lib/api";
import { formatInr, swatchForColor } from "@/lib/color-swatch";
import { restoreSnapshot, saveSnapshot, type ConversationMessage } from "@/lib/search-session";
import { ShopifyProductsGrid } from "@/app/shopify-search-panel";
import { ShopifyChatPanel, type ShopifyChatMessage } from "@/app/shopify-chat-panel";

type ViewState = {
  status: "idle" | "loading" | "error" | "ready";
  data: ConversationalSearchResponse | null;
  error: string | null;
  messages: ConversationMessage[];
};

type SearchUpdate = {
  field: ConstraintField;
  operation: "REMOVE" | "SET";
  value?: string | number;
  inclusive?: boolean | null;
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

function ShopifyLanding({
  draft, setDraft, onSubmit, busy, error,
}: {
  draft: string;
  setDraft: (value: string) => void;
  onSubmit: (event: React.SyntheticEvent) => void;
  busy: boolean;
  error: string | null;
}) {
  return (
    <div>
      <div className="shopify-hero relative isolate grid overflow-hidden rounded-[2rem] border border-[#e5dfd4] bg-[#eee9df] shadow-[0_28px_80px_-54px_rgba(41,37,36,0.45)] lg:min-h-[510px] lg:grid-cols-[1fr_0.92fr]">
        <div className="relative z-10 flex flex-col justify-center px-6 py-10 sm:px-10 sm:py-14 lg:px-14 lg:py-16">
          <p className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.23em] text-stone-600"><span className="size-1.5 rounded-full bg-emerald-700" /> Live from Shopify merchants</p>
          <h1 className="mt-5 max-w-xl font-serif text-[2.7rem] leading-[1.04] tracking-tight text-[#292720] sm:text-6xl">Good finds.<br /><span className="italic text-[#8a5947]">Found for you.</span></h1>
          <p className="mt-5 max-w-md text-sm leading-6 text-stone-600 sm:text-base sm:leading-7">Explore independent merchant collections with one natural search. Refine by style, size and budget as you go.</p>
          <form onSubmit={onSubmit} className="mt-8 max-w-xl rounded-2xl border border-white/80 bg-white/90 p-2 shadow-sm backdrop-blur">
            <label htmlFor="shopify-landing-query" className="sr-only">Search live Shopify products</label>
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className="pl-3 text-xl text-stone-400">⌕</span>
              <input id="shopify-landing-query" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Try ‘blue cotton kurta under ₹1,500’" className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-stone-400" />
              <button type="submit" disabled={busy || !draft.trim()} className="shrink-0 rounded-xl bg-stone-900 px-4 py-3 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">{busy ? "Searching…" : "Explore"}</button>
            </div>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            {["Summer cotton", "Wedding guest", "Everyday under ₹2,000"].map((idea) => <button type="button" key={idea} onClick={() => setDraft(idea)} className="rounded-full border border-stone-400/60 bg-white/40 px-3.5 py-2 text-[11px] text-stone-700 transition hover:border-stone-700 hover:bg-white/75">{idea}</button>)}
          </div>
          {busy && <p className="mt-4 text-sm text-stone-500" role="status">Searching live Shopify listings…</p>}
          {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
          <div className="mt-9 flex flex-wrap gap-x-7 gap-y-3 border-t border-stone-400/30 pt-5 text-[10px] font-medium uppercase tracking-[0.15em] text-stone-500">
            <span>Live merchant offers</span><span>Price-aware search</span><span>Nothing copied locally</span>
          </div>
        </div>

        <div className="relative min-h-[330px] overflow-hidden sm:min-h-[420px] lg:min-h-[510px]">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_42%,rgba(255,255,255,0.76),transparent_52%),linear-gradient(140deg,#e5d9ca,#d9d8c9_54%,#b9c1ae)]" />
          <div className="absolute -right-14 top-10 size-60 rounded-full border border-white/40 sm:size-80" />
          <div className="absolute right-2 top-20 size-48 rounded-full border border-white/35 sm:right-8 sm:top-24 sm:size-64" />
          <div className="absolute bottom-0 left-0 right-0 h-24 bg-[linear-gradient(transparent,rgba(74,66,54,0.1))]" />
          <div className="absolute left-[8%] top-[13%] w-[68%] max-w-[340px] rotate-[-5deg] overflow-hidden rounded-[1.25rem] border border-white/75 bg-[#f7f3ea] p-2 shadow-[0_28px_55px_-24px_rgba(50,44,35,0.42)]">
            <svg viewBox="0 0 360 390" role="img" aria-label="Decorative illustration of a blue cotton kurta and fabric swatches" className="block w-full rounded-[0.9rem]">
              <defs>
                <linearGradient id="hero-paper" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f4ecdf"/><stop offset="1" stopColor="#e1e7da"/></linearGradient>
                <linearGradient id="hero-blue" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#6d8790"/><stop offset=".52" stopColor="#405e68"/><stop offset="1" stopColor="#2d4853"/></linearGradient>
                <linearGradient id="hero-rose" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#c58f79"/><stop offset="1" stopColor="#a76e5e"/></linearGradient>
              </defs>
              <rect width="360" height="390" fill="url(#hero-paper)" />
              <path d="M24 304c54-46 110-32 150 7s91 39 162-12v91H24z" fill="#c6cebd" opacity=".65" />
              <circle cx="285" cy="76" r="39" fill="#d3b48d" opacity=".65" />
              <path d="M115 69l35-14 30 26 29-26 36 14 47 33-25 52-24-14 9 186H80l10-186-25 14-25-52z" fill="url(#hero-blue)" />
              <path d="M150 55l30 26-23 31-29-33zM209 55l-29 26 23 31 29-33z" fill="#e6ded0" />
              <path d="M180 81v80m-5-50h10m-10 19h10m-10 19h10" stroke="#d3b48d" strokeWidth="3" strokeLinecap="round" />
              <path d="M105 195c26 10 47 11 67 2m16 0c21 9 44 8 68-2" fill="none" stroke="#d0bd9c" strokeWidth="2" opacity=".8" />
              <path d="M124 222h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16" stroke="#d0bd9c" strokeWidth="2" opacity=".75" />
              <path d="M219 222h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16m-16 14h16" stroke="#d0bd9c" strokeWidth="2" opacity=".75" />
              <rect x="25" y="28" width="64" height="38" rx="4" fill="url(#hero-rose)" transform="rotate(-8 25 28)" />
              <rect x="279" y="318" width="50" height="39" rx="4" fill="#d9c7a9" transform="rotate(10 279 318)" />
              <text x="24" y="365" fill="#665d50" fontSize="9" letterSpacing="2.2" fontFamily="Arial, sans-serif">THE LIVE STYLE EDIT · 01</text>
            </svg>
          </div>
          <div className="absolute bottom-[12%] right-[8%] w-[34%] max-w-[170px] rotate-[7deg] overflow-hidden rounded-2xl border border-white/80 bg-white/90 p-3 shadow-xl backdrop-blur">
            <div className="flex gap-2"><span className="size-8 rounded-full bg-[#526c71]"/><span className="size-8 rounded-full bg-[#b77d68]"/><span className="size-8 rounded-full bg-[#d3bd99]"/></div>
            <p className="mt-3 text-[9px] font-semibold uppercase tracking-[0.18em] text-stone-500">Fresh from merchants</p>
            <p className="mt-1 font-serif text-sm text-stone-800">Made to be found.</p>
          </div>
          <div className="absolute right-5 top-5 rounded-full border border-white/70 bg-white/55 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.18em] text-stone-600 backdrop-blur">VastraAI · Live edit</div>
        </div>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 px-1 text-xs text-stone-500">
        <span>One search across live Shopify merchant catalogs</span>
        <span>Results, prices and availability are fetched live</span>
      </div>
    </div>
  );
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
  const [provider, setProvider] = useState<"local" | "shopify">("shopify");
  const [shopifyResult, setShopifyResult] = useState<ShopifySearchResponse | null>(null);
  const [shopifyMessages, setShopifyMessages] = useState<ShopifyChatMessage[]>([]);
  const [shopifyPriceMin, setShopifyPriceMin] = useState("");
  const [shopifyPriceMax, setShopifyPriceMax] = useState("");
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

  const execute = useCallback(async (text: string, directUpdate?: SearchUpdate | SearchUpdate[]) => {
    if (inFlightRef.current) return;
    const trimmed = text.trim();
    if (!trimmed && !directUpdate) return;
    inFlightRef.current = true;
    shouldFollowRef.current = true;
    const userMessage: ConversationMessage | null = trimmed ? { id: `${Date.now()}-${Math.random()}`, role: "user", content: trimmed } : null;
    const shopifyUserMessage: ShopifyChatMessage | null = provider === "shopify" && trimmed
      ? { id: `${Date.now()}-${Math.random()}`, role: "user", content: trimmed }
      : null;
    if (shopifyUserMessage) setShopifyMessages((messages) => [...messages, shopifyUserMessage]);
    setView((current) => ({
      ...current,
      status: "loading",
      error: null,
      messages: provider === "local" && userMessage ? [...current.messages, userMessage] : current.messages,
    }));
    setDraft("");
    try {
      if (provider === "shopify") {
        const current = shopifyResult;
        const updates = directUpdate
          ? Array.isArray(directUpdate) ? directUpdate : [directUpdate]
          : undefined;
        const result = await fetchShopifySearch(current?.session_id && current.revision !== undefined
          ? {
              session_id: current.session_id,
              expected_revision: current.revision,
              ...(updates ? { updates } : { message: trimmed }),
              limit: 12,
            }
          : trimmed, 12);
        setShopifyResult(result);
        setShopifyPriceMin(String(result.state?.constraints.price_min ?? ""));
        setShopifyPriceMax(String(result.state?.constraints.price_max ?? ""));
        const reply = result.answer || (result.total === 0
          ? "I couldn’t find live listings for those preferences. Try broadening the search or removing a filter."
          : `I found ${result.total} live Shopify ${result.total === 1 ? "listing" : "listings"}. You can refine by style, size or budget.`);
        setShopifyMessages((messages) => [...messages, {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: reply,
          productIds: result.referenced_product_ids,
        }]);
        setView((previous) => ({ ...previous, status: "ready", error: null }));
        return;
      }
      const current = view.data;
      const updates = directUpdate
        ? Array.isArray(directUpdate) ? directUpdate : [directUpdate]
        : undefined;
      const data = await fetchConversationalSearch(current
        ? {
            session_id: current.session_id,
            expected_revision: current.revision,
            ...(updates ? { updates } : { message: trimmed }),
            limit: 12,
          }
        : { query: trimmed, limit: 12 });
      const reply = data.answer || (data.search_status === "off_topic"
        ? "I can help you find clothing, footwear and accessories. Tell me what you are shopping for."
        : data.total === 0
          ? "I couldn’t find an exact match for those preferences. You can remove a filter to broaden your selection."
          : "I found options that match your preferences.");
      const assistantMessage: ConversationMessage = { id: `${Date.now()}-assistant`, role: "assistant", content: reply, productIds: data.referenced_product_ids };
      setView((previous) => ({ status: "ready", data, error: null, messages: [...previous.messages, assistantMessage] }));
      setConversationOpen(true);
    } catch (error: unknown) {
      const message = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Your search could not be updated.";
      // Preserve the attempted turn in the transcript while the confirmed state and products remain intact.
      setView((previous) => ({ ...previous, status: "ready", error: message }));
    } finally {
      inFlightRef.current = false;
    }
  }, [view.data, provider, shopifyResult]);

  function onSubmit(event: React.SyntheticEvent) {
    event.preventDefault();
    void execute(draft);
  }

  function removeFilter(field: ConstraintField) {
    void execute("", { field, operation: "REMOVE" });
  }

  function applyShopifyPriceRange(event: React.SyntheticEvent) {
    event.preventDefault();
    const updates: SearchUpdate[] = [
      shopifyPriceMin.trim()
        ? { field: "price_min", operation: "SET", value: Number(shopifyPriceMin), inclusive: true }
        : { field: "price_min", operation: "REMOVE" },
      shopifyPriceMax.trim()
        ? { field: "price_max", operation: "SET", value: Number(shopifyPriceMax), inclusive: true }
        : { field: "price_max", operation: "REMOVE" },
    ];
    void execute("", updates);
  }

  function startNewSearch() {
    setDraft("");
    setColorChoicesOpen(false);
    setView(initialState);
    setShopifyResult(null);
    setShopifyMessages([]);
    setShopifyPriceMin("");
    setShopifyPriceMax("");
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
            <label htmlFor="search-provider" className="sr-only">Search provider</label>
            <select
              id="search-provider"
              value={provider}
              onChange={(event) => {
                setProvider(event.target.value as "local" | "shopify");
                setView((current) => ({ ...current, error: null }));
              }}
              disabled={busy}
              className="mr-2 max-w-24 bg-transparent text-xs text-stone-600 outline-none"
            >
              <option value="local">VastraAI</option>
              <option value="shopify">Shopify</option>
            </select>
            <span aria-hidden="true" className="mr-3 text-stone-400">⌕</span>
            <input
              aria-label="Search products, styles or occasions"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }}
              placeholder={provider === "shopify" ? shopifyResult ? "Refine Shopify results…" : "Search Shopify products…" : "Search products, styles or occasions…"}
              className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-stone-400"
            />
            <button type="submit" disabled={busy || !draft.trim()} className="ml-2 rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Search</button>
          </form>
          <Link href="/catalog" className="hidden text-sm text-stone-600 transition hover:text-stone-950 sm:block">Catalog</Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-4 pb-16 pt-5 sm:px-7 sm:pt-8">
        {provider === "shopify" ? (
          <section className="min-h-[55vh]" aria-busy={busy}>
            {!shopifyResult ? (
              <ShopifyLanding draft={draft} setDraft={setDraft} onSubmit={onSubmit} busy={busy} error={view.error} />
            ) : (
              <div className="grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-9">
                <div className="min-w-0">
                  <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">Live Shopify catalog</p>
                      <h1 className="mt-2 font-serif text-3xl capitalize tracking-tight sm:text-4xl">{shopifyResult.query}</h1>
                      {busy && <p role="status" className="mt-2 text-sm text-stone-500">Searching Shopify products…</p>}
                    </div>
                    <button type="button" onClick={startNewSearch} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-xs text-stone-600 transition hover:border-stone-500 hover:text-stone-900">New search</button>
                  </div>
                  {shopifyResult.active_filters?.length ? <div className="mb-5 flex flex-wrap gap-2" aria-label="Active Shopify filters">{shopifyResult.active_filters.map((filter) => <button key={filter.key} onClick={() => removeFilter(filter.key)} disabled={busy} aria-label={`Remove ${filter.label}: ${filter.value}`} className="rounded-full border border-stone-300 bg-white px-3.5 py-1.5 text-xs text-stone-700 transition hover:border-stone-600 disabled:opacity-50">{filter.value} <span aria-hidden="true" className="ml-1 text-stone-400">×</span></button>)}</div> : null}
                  {shopifyResult.session_id && <form onSubmit={applyShopifyPriceRange} className="mb-6 flex flex-wrap items-end gap-3 rounded-2xl border border-stone-200 bg-white p-4"><label className="text-xs text-stone-600">Minimum price ({String(shopifyResult.state?.constraints.currency ?? "INR")})<input aria-label="Shopify minimum price" type="number" min="0" step="1" value={shopifyPriceMin} onChange={(event) => setShopifyPriceMin(event.target.value)} className="mt-1 block w-32 rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900" /></label><label className="text-xs text-stone-600">Maximum price ({String(shopifyResult.state?.constraints.currency ?? "INR")})<input aria-label="Shopify maximum price" type="number" min="0" step="1" value={shopifyPriceMax} onChange={(event) => setShopifyPriceMax(event.target.value)} className="mt-1 block w-32 rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-900" /></label><button type="submit" disabled={busy} className="rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white disabled:opacity-40">Apply price filters</button><span className="text-xs text-stone-500">Filters live offers; seller prices stay unchanged.</span></form>}
                  {shopifyResult.results.length ? <ShopifyProductsGrid result={shopifyResult} /> : <div className="rounded-3xl border border-stone-200 bg-white px-6 py-12 text-center"><span className="text-3xl" aria-hidden="true">⌕</span><h2 className="mt-3 font-serif text-2xl">No live listings found</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-stone-600">Try a wider price range or ask VastraAI to adjust your search.</p></div>}
                </div>
                <aside className="xl:sticky xl:top-[88px]">
                  <ShopifyChatPanel messages={shopifyMessages} products={shopifyResult.results} draft={draft} setDraft={setDraft} onSubmit={onSubmit} busy={busy} error={view.error} />
                </aside>
              </div>
            )}
          </section>
        ) : !data ? (
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
              <ConversationPanel view={view} draft={draft} setDraft={setDraft} onSubmit={onSubmit} transcriptRef={transcriptRef} shouldFollowRef={shouldFollowRef} busy={busy} />
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

      {conversationOpen && provider === "local" && data && <div className="fixed inset-0 z-50 flex items-end bg-stone-950/35 lg:hidden" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setConversationOpen(false); }}><section role="dialog" aria-modal="true" aria-label="VastraAI shopping conversation" className="max-h-[90dvh] w-full overflow-hidden rounded-t-[1.5rem] bg-[#fbfaf8] p-4 shadow-2xl"><div className="mx-auto mb-3 h-1 w-10 rounded-full bg-stone-300" /><div className="mb-3 flex items-center justify-between"><p className="font-serif text-xl">Shopping with VastraAI</p><button onClick={() => setConversationOpen(false)} aria-label="Close conversation" className="grid size-9 place-items-center rounded-full border border-stone-200">×</button></div><ConversationPanel view={view} draft={draft} setDraft={setDraft} onSubmit={onSubmit} transcriptRef={transcriptRef} shouldFollowRef={shouldFollowRef} busy={busy} compact /></section></div>}
    </div>
  );
}

function ConversationPanel({
  view, draft, setDraft, onSubmit, transcriptRef, shouldFollowRef, busy, compact = false,
}: {
  view: ViewState;
  draft: string;
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
      {view.messages.map((message) => <div key={message.id} className={message.role === "user" ? "ml-6" : "mr-4"}><p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.17em] text-stone-500">{message.role === "user" ? "You" : "VastraAI"}</p><div className={`rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-tr-md bg-stone-900 text-white" : "rounded-tl-md bg-[#f5f3ef] text-stone-700"}`}>{message.content}</div>{message.productIds?.length ? <div className="mt-2 flex flex-wrap gap-1.5">{message.productIds.map((id) => { const product = data?.results.find((item) => item.product_id === id); return product ? <Link key={id} href={product.product_url} className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[10px] text-stone-600 underline-offset-2 hover:underline">{product.title}</Link> : null; })}</div> : null}</div>)}
      {busy && <div className="mr-8 rounded-2xl rounded-tl-md bg-[#f5f3ef] px-4 py-3 text-xs text-stone-500"><span className="mr-2 inline-flex gap-1" aria-hidden="true"><i className="size-1.5 animate-pulse rounded-full bg-stone-500" /><i className="size-1.5 animate-pulse rounded-full bg-stone-400 [animation-delay:120ms]" /><i className="size-1.5 animate-pulse rounded-full bg-stone-300 [animation-delay:240ms]" /></span>Updating your selection</div>}
      {view.error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-800">{view.error} Your current selection is unchanged.</p>}
      {data && <p className="text-center text-[10px] text-stone-400">Your preferences are saved in this search</p>}
    </div>
    <form onSubmit={onSubmit} className="border-t border-stone-100 p-3">
      <label htmlFor={compact ? "mobile-refinement" : "desktop-refinement"} className="sr-only">Message VastraAI</label>
      <div className="rounded-2xl border border-stone-300 bg-white p-2 focus-within:border-stone-500 focus-within:ring-2 focus-within:ring-stone-100"><textarea id={compact ? "mobile-refinement" : "desktop-refinement"} value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }} placeholder="Make it blue, size M…" rows={2} className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-stone-400"/><div className="flex items-center justify-between px-1"><span className="text-[10px] text-stone-400">Enter to send · Shift + Enter for a new line</span><button disabled={busy || !draft.trim()} className="rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Send</button></div></div>
    </form>
  </section>;
}
