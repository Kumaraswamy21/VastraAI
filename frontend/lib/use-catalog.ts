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
  const key = JSON.stringify(query);
  const [state, setState] = useState<{ key: string; value: CatalogState }>({
    key,
    value: { kind: "loading" },
  });

  useEffect(() => {
    const controller = new AbortController();
    const requestQuery = JSON.parse(key) as CatalogQuery;
    fetchProducts(requestQuery, controller.signal)
      .then((data) => setState({ key, value: { kind: "ready", data } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const message = error instanceof Error ? error.message : "Catalog request failed";
        setState({ key, value: { kind: "error", message } });
      });
    return () => controller.abort();
  }, [key]);

  return state.key === key ? state.value : { kind: "loading" };
}
