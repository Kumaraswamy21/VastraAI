"use client";

import { useRouter, useSearchParams } from "next/navigation";
import type { CatalogQuery } from "@/lib/api";
import { catalogPath, catalogQueryFromSearchParams } from "@/lib/catalog-query";
import { useCatalog } from "@/lib/use-catalog";
import { FilterDrawer } from "./filter-drawer";
import { FilterPanel } from "./filter-panel";
import { Pagination } from "./pagination";
import { ProductCard } from "./product-card";

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
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <p className="text-sm font-medium tracking-wide text-zinc-500">AI Fashion Search</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-900">Catalog</h1>
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
