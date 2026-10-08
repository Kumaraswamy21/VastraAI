"use client";

import Link from "next/link";
import { formatInr, swatchForColor } from "@/lib/color-swatch";
import { useProduct } from "@/lib/use-product";

export function ProductDetail({ slug }: { slug: string }) {
  const state = useProduct(slug);

  if (state.kind === "loading") {
    return <p className="p-8 text-sm text-zinc-500">Loading product…</p>;
  }
  if (state.kind === "missing") {
    return (
      <main className="p-8">
        <h1 className="text-xl font-semibold">Product not found</h1>
        <Link href="/catalog" className="mt-4 inline-block text-sm text-zinc-600 underline">
          Back to catalog
        </Link>
      </main>
    );
  }
  if (state.kind === "error") {
    return <p className="p-8 text-sm text-red-700">{state.message}</p>;
  }

  const product = state.product;
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/catalog" className="text-sm text-zinc-600 underline">
        Back to catalog
      </Link>
      <div
        className="h-56 rounded-xl"
        style={{ backgroundColor: swatchForColor(product.color) }}
      />
      <div>
        <p className="text-sm capitalize text-zinc-500">{product.category}</p>
        <h1 className="mt-1 text-2xl font-semibold text-zinc-900">{product.title}</h1>
        <p className="mt-2 text-lg font-medium text-zinc-900">{formatInr(product.price_inr)}</p>
      </div>
      <p className="text-sm leading-6 text-zinc-600">{product.description}</p>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <Detail label="Color" value={product.color} />
        <Detail label="Gender" value={product.gender} />
        <Detail label="Occasion" value={product.occasion} />
        <Detail label="Style" value={product.style} />
        <Detail label="Material" value={product.material} />
        <Detail label="Sizes" value={product.sizes.join(", ")} />
      </dl>
    </main>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-zinc-500">{label}</dt>
      <dd className="capitalize text-zinc-900">{value}</dd>
    </div>
  );
}
