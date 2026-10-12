"use client";

import { useState } from "react";
import {
  ApiError,
  fetchShopifySearch,
  type ShopifyProductResult,
  type ShopifySearchResponse,
} from "@/lib/api";

function formatPrice(amount: number | string | null | undefined, currency: string | null | undefined) {
  if (amount == null || !currency) return null;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(Number(amount));
  } catch {
    return `${amount} ${currency}`;
  }
}

function ShopifyCard({ product }: { product: ShopifyProductResult }) {
  const minimum = formatPrice(product.price_min, product.currency);
  const maximum = formatPrice(product.price_max, product.currency);
  const price = minimum && maximum && minimum !== maximum
    ? `${minimum}–${maximum}`
    : minimum ?? "See seller for price";
  const productUrl = product.product_url ?? product.merchant_url;
  const content = (
    <>
      <div className="group relative overflow-hidden bg-[linear-gradient(145deg,#eee9df,#e4e5dc)]">
        {product.image_url ? (
          // Shopify requires catalog images to be rendered from their live URL.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={product.image_url} alt={product.image_alt ?? product.title} className="aspect-[4/4.6] w-full object-cover transition duration-500 group-hover:scale-[1.035]" loading="lazy" />
        ) : (
          <div className="grid aspect-[4/4.6] place-items-center text-xs text-stone-500"><span className="rounded-full border border-white/70 bg-white/60 px-4 py-2 backdrop-blur">Image unavailable</span></div>
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-stone-950/25 to-transparent" />
        <span className="absolute left-3 top-3 rounded-full border border-white/70 bg-white/85 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.15em] text-stone-700 backdrop-blur">Live offer</span>
        {product.available === false && <span className="absolute bottom-3 left-3 rounded-full bg-stone-900/80 px-2.5 py-1 text-[9px] font-medium text-white">Currently unavailable</span>}
      </div>
      <div className="p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-500">{product.merchant_name ?? "Shopify merchant"}</p>
        <h3 className="mt-1.5 line-clamp-2 min-h-10 text-sm font-medium leading-5 text-stone-900">{product.title}</h3>
        <p className="mt-2 text-base font-semibold text-stone-900">{price}</p>
        {product.available === true && <p className="mt-2 text-xs text-stone-600">Available</p>}
        {product.available === false && <p className="mt-2 text-xs text-stone-500">Currently unavailable</p>}
        <p className="mt-3 border-t border-stone-100 pt-3 text-xs text-stone-600">{productUrl ? "View product at merchant ↗" : "Merchant link unavailable"}</p>
      </div>
    </>
  );

  return productUrl ? (
    <a
      href={productUrl}
      target="_blank"
      rel="noreferrer"
      className="group overflow-hidden rounded-2xl border border-stone-200/80 bg-white transition duration-200 hover:-translate-y-0.5 hover:border-stone-400 hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-700"
    >
      {content}
    </a>
  ) : (
    <article className="overflow-hidden rounded-2xl border border-stone-200/80 bg-white">
      {content}
    </article>
  );
}

export function ShopifyProductsGrid({ result }: { result: ShopifySearchResponse }) {
  return (
    <>
      <p className="mb-4 text-sm text-stone-600" role="status">
        {result.total ? `${result.total} Shopify ${result.total === 1 ? "product" : "products"}` : "No Shopify products found"}
        {result.has_next_page ? " · More results are available" : ""}
      </p>
      {result.results.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:gap-5 xl:grid-cols-3" aria-label="Shopify search results">
          {result.results.map((product) => <ShopifyCard key={product.product_id} product={product} />)}
        </div>
      )}
    </>
  );
}

export function ShopifySearchPanel() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<ShopifySearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.SyntheticEvent) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await fetchShopifySearch(trimmed));
    } catch (cause) {
      setError(cause instanceof ApiError || cause instanceof Error
        ? cause.message
        : "Shopify catalog search is unavailable.");
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto mt-12 max-w-[1440px] border-t border-stone-200 pt-8" aria-labelledby="shopify-heading">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">Independent catalog</p>
          <h2 id="shopify-heading" className="mt-2 font-serif text-2xl">Explore Shopify products</h2>
          <p className="mt-1 text-sm text-stone-600">Search available products from Shopify merchants.</p>
        </div>
        <form onSubmit={submit} className="flex w-full max-w-xl gap-2">
          <label htmlFor="shopify-query" className="sr-only">Search Shopify products</label>
          <input
            id="shopify-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={500}
            placeholder="Linen shirt, evening bag…"
            className="h-11 min-w-0 flex-1 rounded-full border border-stone-300 bg-white px-4 text-sm outline-none focus:border-stone-500 focus:ring-2 focus:ring-stone-200"
          />
          <button type="submit" disabled={busy || !query.trim()} className="rounded-full bg-stone-900 px-5 py-2 text-xs font-medium text-white transition hover:bg-stone-700 disabled:opacity-40">
            {busy ? "Searching…" : "Search Shopify"}
          </button>
        </form>
      </div>
      {error && <p role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>}
      {result && (
        <div className="mt-6">
          <ShopifyProductsGrid result={result} />
        </div>
      )}
    </section>
  );
}
