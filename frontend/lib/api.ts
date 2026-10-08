export type HealthPayload = {
  status: string;
  backend: string;
  database: string;
};

export type Product = {
  id: number;
  title: string;
  category: string;
  color: string;
  material: string;
  occasion: string;
  style: string;
  gender: string;
  sizes: string[];
  price_inr: number;
  description: string;
  image_reference: string;
  slug: string;
  product_url: string;
};

export type ProductListResponse = {
  items: Product[];
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
};

export type CatalogQuery = {
  page?: number;
  page_size?: number;
  category?: string;
  color?: string;
  gender?: string;
  occasion?: string;
  style?: string;
  size?: string;
  min_price?: number;
  max_price?: number;
  sort?: "newest" | "price_asc" | "price_desc";
};

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed: ${response.status}`);
  }
  return response.json();
}

export async function fetchHealth(): Promise<HealthPayload> {
  return readJson(await fetch(`${apiBase()}/health`));
}

export function isHealthy(value: string | undefined): boolean {
  return value === "ok";
}

export function catalogQueryToParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, query);
  return params;
}

function appendDefined(params: URLSearchParams, query: CatalogQuery): void {
  const entries: [string, string | number | undefined][] = [
    ["page", query.page],
    ["page_size", query.page_size],
    ["category", query.category],
    ["color", query.color],
    ["gender", query.gender],
    ["occasion", query.occasion],
    ["style", query.style],
    ["size", query.size],
    ["min_price", query.min_price],
    ["max_price", query.max_price],
    ["sort", query.sort],
  ];
  for (const [key, value] of entries) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
}

export async function fetchProducts(
  query: CatalogQuery,
  signal?: AbortSignal,
): Promise<ProductListResponse> {
  const params = catalogQueryToParams(query);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return readJson(await fetch(`${apiBase()}/products${suffix}`, { signal }));
}

export async function fetchProduct(
  slug: string,
  signal?: AbortSignal,
): Promise<Product> {
  return readJson(await fetch(`${apiBase()}/products/${slug}`, { signal }));
}
