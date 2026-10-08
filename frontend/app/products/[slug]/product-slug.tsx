"use client";

import { useParams } from "next/navigation";
import { ProductDetail } from "./product-detail";

export function ProductSlug() {
  const params = useParams<{ slug: string }>();
  const slug = typeof params.slug === "string" ? params.slug : "";
  if (!slug) {
    return <p className="p-8 text-sm text-zinc-500">Loading product…</p>;
  }
  return <ProductDetail slug={slug} />;
}
