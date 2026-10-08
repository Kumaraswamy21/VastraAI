"use client";

import { useEffect, useState } from "react";
import {
  fetchProducts,
  type CatalogQuery,
  type ProductListResponse,
} from "@/lib/api";

type CatalogState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: ProductListResponse };

export function useCatalog(query: CatalogQuery): CatalogState {
  const [state, setState] = useState<CatalogState>({ kind: "loading" });
  const key = JSON.stringify(query);

  useEffect(() => {
    const controller = new AbortController();
    setState({ kind: "loading" });
    fetchProducts(query, controller.signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Catalog request failed";
        setState({ kind: "error", message });
      });
    return () => controller.abort();
  }, [key]);

  return state;
}
