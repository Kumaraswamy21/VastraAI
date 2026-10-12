"use client";

import { useEffect, useRef } from "react";
import type { ShopifyProductResult } from "@/lib/api";

export type ShopifyChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  productIds?: string[];
};

export function ShopifyChatPanel({
  messages,
  products,
  draft,
  setDraft,
  onSubmit,
  busy,
  error,
}: {
  messages: ShopifyChatMessage[];
  products: ShopifyProductResult[];
  draft: string;
  setDraft: (value: string) => void;
  onSubmit: (event: React.SyntheticEvent) => void;
  busy: boolean;
  error: string | null;
}) {
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (transcript) transcript.scrollTo({ top: transcript.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  return (
    <section aria-label="Shopify shopping chat" className="flex h-[min(720px,calc(100dvh-110px))] min-h-[520px] flex-col overflow-hidden rounded-[1.5rem] border border-stone-200 bg-white shadow-[0_18px_55px_-38px_rgba(41,37,36,0.45)]">
      <div className="border-b border-stone-100 bg-[linear-gradient(135deg,#faf8f4,#f3f0e9)] px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-full bg-stone-900 text-sm font-semibold text-white">V</span>
          <div className="min-w-0">
            <h2 className="font-serif text-lg text-stone-900">Your style concierge</h2>
            <p className="flex items-center gap-1.5 text-[11px] text-stone-500"><span className="size-1.5 rounded-full bg-emerald-600" /> Connected to live Shopify results</p>
          </div>
        </div>
      </div>

      <div ref={transcriptRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5" aria-live="polite">
        {!messages.length && (
          <div className="rounded-2xl bg-[#f7f5f1] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-500">VastraAI · Live shopping</p>
            <p className="mt-2 text-sm leading-6 text-stone-700">Tell me what you have in mind. I’ll search current merchant listings and help you refine the results.</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {["Under ₹1,500", "More summer options", "Sort by lowest price"].map((suggestion) => (
                <button key={suggestion} type="button" onClick={() => setDraft(suggestion)} className="rounded-full border border-stone-300 bg-white px-3 py-1.5 text-[11px] text-stone-600 transition hover:border-stone-600 hover:text-stone-900">{suggestion}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div key={message.id} className={message.role === "user" ? "ml-7" : "mr-5"}>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-stone-400">{message.role === "user" ? "You" : "VastraAI"}</p>
            <div className={`rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "rounded-tr-md bg-stone-900 text-white" : "rounded-tl-md bg-[#f5f3ef] text-stone-700"}`}>{message.content}</div>
            {message.productIds?.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {message.productIds.map((id) => {
                  const product = products.find((item) => item.product_id === id);
                  const url = product?.product_url ?? product?.merchant_url;
                  return product && url ? <a key={id} href={url} target="_blank" rel="noreferrer" className="max-w-full truncate rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[10px] text-stone-600 underline-offset-2 hover:underline">{product.title} ↗</a> : null;
                })}
              </div>
            ) : null}
          </div>
        ))}

        {busy && <div className="mr-8 rounded-2xl rounded-tl-md bg-[#f5f3ef] px-4 py-3 text-xs text-stone-500"><span className="mr-2 inline-flex gap-1" aria-hidden="true"><i className="size-1.5 animate-pulse rounded-full bg-stone-500" /><i className="size-1.5 animate-pulse rounded-full bg-stone-400 [animation-delay:120ms]" /><i className="size-1.5 animate-pulse rounded-full bg-stone-300 [animation-delay:240ms]" /></span>Checking live listings</div>}
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-800">{error}</p>}
        <p className="text-center text-[10px] text-stone-400">Prices and availability come from current merchant listings.</p>
      </div>

      <form onSubmit={onSubmit} className="border-t border-stone-100 p-3">
        <label htmlFor="shopify-chat-message" className="sr-only">Refine your Shopify search</label>
        <div className="rounded-2xl border border-stone-300 bg-white p-2 transition focus-within:border-stone-500 focus-within:ring-2 focus-within:ring-stone-100">
          <textarea id="shopify-chat-message" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); onSubmit(event); } }} placeholder="Try ‘blue, under ₹1,500’…" rows={2} className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-stone-400" />
          <div className="flex items-center justify-between px-1"><span className="text-[10px] text-stone-400">Enter to send · Shift + Enter for a new line</span><button type="submit" disabled={busy || !draft.trim()} className="rounded-full bg-stone-900 px-4 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Send</button></div>
        </div>
      </form>
    </section>
  );
}
