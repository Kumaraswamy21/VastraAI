import type { CatalogQuery } from "@/lib/api";

const FILTER_KEYS = [
  "category",
  "color",
  "gender",
  "occasion",
  "style",
  "size",
] as const;

export function catalogQueryFromSearchParams(
  params: URLSearchParams,
): CatalogQuery {
  return {
    page: optionalPositiveInt(params.get("page")),
    page_size: optionalPositiveInt(params.get("page_size")),
    category: optionalText(params.get("category")),
    color: optionalText(params.get("color")),
    gender: optionalText(params.get("gender")),
    occasion: optionalText(params.get("occasion")),
    style: optionalText(params.get("style")),
    size: optionalText(params.get("size")),
    min_price: optionalPositiveInt(params.get("min_price")),
    max_price: optionalPositiveInt(params.get("max_price")),
    sort: optionalSort(params.get("sort")),
  };
}

export function catalogPath(query: CatalogQuery): string {
  const params = new URLSearchParams();
  writeQuery(params, query);
  const encoded = params.toString();
  return encoded ? `/catalog?${encoded}` : "/catalog";
}

function writeQuery(params: URLSearchParams, query: CatalogQuery): void {
  if (query.page && query.page > 1) params.set("page", String(query.page));
  if (query.page_size && query.page_size !== 24) {
    params.set("page_size", String(query.page_size));
  }
  for (const key of FILTER_KEYS) {
    const value = query[key];
    if (value) params.set(key, value);
  }
  if (query.min_price !== undefined) params.set("min_price", String(query.min_price));
  if (query.max_price !== undefined) params.set("max_price", String(query.max_price));
  if (query.sort && query.sort !== "newest") params.set("sort", query.sort);
}

function optionalText(value: string | null): string | undefined {
  if (!value) return undefined;
  return value;
}

function optionalPositiveInt(value: string | null): number | undefined {
  if (!value) return undefined;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) return undefined;
  return parsed;
}

function optionalSort(
  value: string | null,
): CatalogQuery["sort"] | undefined {
  if (value === "newest" || value === "price_asc" || value === "price_desc") {
    return value;
  }
  return undefined;
}
