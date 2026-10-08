"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchProduct, type Product } from "@/lib/api";

type ProductState =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "error"; message: string }
  | { kind: "ready"; product: Product };

export function useProduct(slug: string): ProductState {
  const [state, setState] = useState<ProductState>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchProduct(slug, controller.signal)
      .then((product) => setState({ kind: "ready", product }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 404) {
          setState({ kind: "missing" });
          return;
        }
        const message = error instanceof Error ? error.message : "Product request failed";
        setState({ kind: "error", message });
      });
    return () => controller.abort();
  }, [slug]);

  return state;
}
