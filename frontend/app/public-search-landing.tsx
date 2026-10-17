"use client";

import Link from "next/link";
import { useState } from "react";

const suggestions = ["Wedding guest looks", "Everyday linen", "A blue kurta"];

export function PublicSearchLanding() {
  const [query, setQuery] = useState("");
  const [pendingQuery, setPendingQuery] = useState("");

  function submitSearch(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    setPendingQuery(trimmed.slice(0, 300));
  }

  const returnTo = `/?${new URLSearchParams({ query: pendingQuery })}`;
  const authParams = new URLSearchParams({ callbackUrl: returnTo });

  return (
    <div className="flex min-h-screen flex-col bg-[#f7f5f1] text-stone-900">
      <header className="border-b border-stone-200/80 bg-[#fbfaf8] px-5 py-4 sm:px-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          <Link href="/" className="font-serif text-xl tracking-tight">VastraAI</Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link href="/catalog" className="text-stone-600 hover:text-stone-950">Browse catalog</Link>
            <Link href="/sign-in" className="rounded-full border border-stone-300 bg-white px-4 py-2 font-medium hover:border-stone-500">Sign in</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center px-5 py-16 text-center sm:py-24">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-stone-500">A considered way to shop</p>
        <h1 className="mt-5 max-w-3xl font-serif text-5xl leading-tight tracking-tight sm:text-7xl">Find the pieces that feel like you.</h1>
        <p className="mt-6 max-w-xl text-sm leading-7 text-stone-600 sm:text-base">Describe a piece, an occasion or a feeling. Search in your own words and shape your selection as you go.</p>

        <form onSubmit={submitSearch} className="mt-10 w-full max-w-2xl rounded-[1.75rem] border border-stone-200 bg-white p-3 text-left shadow-sm">
          <label htmlFor="landing-search" className="sr-only">Describe what you are looking for</label>
          <textarea
            id="landing-search"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPendingQuery(""); }}
            onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitSearch(event); } }}
            rows={2}
            maxLength={300}
            placeholder="A blue cotton kurta under ₹2,000…"
            className="w-full resize-none bg-transparent px-4 py-3 text-base outline-none placeholder:text-stone-400"
          />
          <div className="flex items-center justify-between gap-3 px-2 pb-1">
            <span className="text-xs text-stone-400">Describe it naturally · Enter to search</span>
            <button type="submit" disabled={!query.trim()} className="rounded-full bg-stone-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">Find my look</button>
          </div>
        </form>
        {pendingQuery && <section aria-live="polite" className="mt-5 w-full max-w-2xl rounded-2xl border border-stone-200 bg-white px-6 py-6 text-left shadow-sm">
          <h2 className="font-serif text-2xl">Your search is ready</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">Sign in or create an account to see results for “{pendingQuery}”.</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Link href={`/sign-in?${authParams}`} className="rounded-full bg-stone-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-stone-700">Already have an account? Log in</Link>
            <Link href={`/register?${authParams}`} className="rounded-full border border-stone-300 bg-white px-5 py-2.5 text-sm font-medium text-stone-800 hover:border-stone-500">New here? Sign up</Link>
          </div>
        </section>}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => { setQuery(suggestion); setPendingQuery(""); }} className="rounded-full border border-stone-300 bg-white/70 px-4 py-2 text-xs text-stone-600 transition hover:border-stone-500 hover:text-stone-900">{suggestion}</button>)}
        </div>
      </main>
    </div>
  );
}
