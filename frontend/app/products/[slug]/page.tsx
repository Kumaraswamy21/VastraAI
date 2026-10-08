import { Suspense } from "react";
import { ProductSlug } from "./product-slug";

export default function ProductPage() {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <p className="text-sm font-medium tracking-wide text-zinc-500">AI Fashion Search</p>
      </header>
      <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading product…</p>}>
        <ProductSlug />
      </Suspense>
    </div>
  );
}
