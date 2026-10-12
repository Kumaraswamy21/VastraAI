"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { CatalogQuery } from "@/lib/api";
import { catalogPath, catalogQueryFromSearchParams } from "@/lib/catalog-query";
import { useCatalog } from "@/lib/use-catalog";
import { FilterDrawer } from "./filter-drawer";
import { FilterPanel } from "./filter-panel";
import { Pagination } from "./pagination";
import { ProductCard } from "./product-card";
import Link from "next/link";

export function CatalogView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const query = catalogQueryFromSearchParams(searchParams);
  const state = useCatalog(query);

  function pushQuery(next: CatalogQuery) {
    router.push(catalogPath(next));
  }

  return (
    <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
      <header className="border-b border-stone-200 bg-[#fbfaf8] px-4 py-4 sm:px-7">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4">
          <Link href="/" className="font-serif text-xl tracking-tight text-stone-900">VastraAI</Link>
          <Link href="/" className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm text-stone-700 transition hover:border-stone-600">Search with VastraAI <span aria-hidden="true">↗</span></Link>
        </div>
        <div className="mx-auto mt-8 max-w-[1440px]"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">The collection</p>
        <h1 className="mt-2 font-serif text-4xl tracking-tight text-stone-900">Pieces for every day, and beyond.</h1>
        <p className="mt-2 text-sm text-stone-600">Browse the edit or let VastraAI help you find the right piece.</p></div>
      </header>
      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-6 md:flex-row md:gap-8">
        <FilterDrawer>
          <FilterPanel query={query} onChange={pushQuery} />
        </FilterDrawer>
        <section className="min-w-0 flex-1">
          <CatalogResults state={state} query={query} onPage={(page) => pushQuery({ ...query, page })} />
        </section>
      </div>
    </div>
  );
}

function CatalogResults({
  state,
  query,
  onPage,
}: {
  state: ReturnType<typeof useCatalog>;
  query: CatalogQuery;
  onPage: (page: number) => void;
}) {
  if (state.kind === "loading") {
    return <p className="py-16 text-center text-sm text-zinc-500">Loading catalog…</p>;
  }
  if (state.kind === "error") {
    return <p className="py-16 text-center text-sm text-red-700">{state.message}</p>;
  }
  if (state.data.items.length === 0) {
    return (
      <p className="py-16 text-center text-sm text-zinc-500">
        No products match these filters.
      </p>
    );
  }
  return (
    <>
      <p className="mb-4 text-sm text-zinc-600">{state.data.total_count} products</p>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
        {state.data.items.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      <Pagination
        page={query.page ?? state.data.page}
        totalPages={state.data.total_pages}
        onPage={onPage}
      />
    </>
  );
}
