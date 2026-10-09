"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchProduct, type Product } from "@/lib/api";

type ProductState =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error"; message: string }
  | { kind: "ready"; product: Product };

export function useProduct(slug: string): ProductState {
  const [state, setState] = useState<{ slug: string; value: ProductState }>({
    slug,
    value: { kind: "loading" },
  });

  useEffect(() => {
    const controller = new AbortController();
    fetchProduct(slug, controller.signal)
      .then((product) => setState({ slug, value: { kind: "ready", product } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ slug, value: { kind: "missing" } });
          return;
        }
        const message = error instanceof Error ? error.message : "Product request failed";
        setState({ slug, value: { kind: "error", message } });
      });
    return () => controller.abort();
  }, [slug]);

  return state.slug === slug ? state.value : { kind: "loading" };
}
