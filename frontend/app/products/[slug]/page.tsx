import { Suspense } from "react";
import Link from "next/link";
import { ProductSlug } from "./product-slug";

export default function ProductPage() {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
      <header className="border-b border-stone-200 bg-[#fbfaf8] px-6 py-4">
        <Link href="/" className="font-serif text-xl tracking-tight text-stone-900">VastraAI</Link>
      </header>
      <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading product…</p>}>
        <ProductSlug />
      </Suspense>
    </div>
  );
}
