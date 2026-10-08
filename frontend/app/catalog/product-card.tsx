import Link from "next/link";
import type { Product } from "@/lib/api";
import { formatInr, swatchForColor } from "@/lib/color-swatch";

export function ProductCard({ product }: { product: Product }) {
  return (
    <Link
      href={product.product_url}
      className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm transition hover:border-zinc-300 hover:shadow"
    >
      <div
        className="flex h-40 items-end p-3"
        style={{ backgroundColor: swatchForColor(product.color) }}
      >
        <span className="rounded bg-white/90 px-2 py-0.5 text-xs font-medium text-zinc-800">
          {product.category}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <h2 className="line-clamp-2 text-sm font-semibold text-zinc-900">{product.title}</h2>
        <p className="text-xs capitalize text-zinc-500">{product.color}</p>
        <p className="mt-auto pt-2 text-sm font-medium text-zinc-900">
          {formatInr(product.price_inr)}
        </p>
      </div>
    </Link>
  );
}
