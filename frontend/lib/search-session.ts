import type { ConversationalSearchResponse } from "./api";

export const SEARCH_SESSION_KEY = "vastraai-search-v1";

export function restoreSearch(storage: Pick<Storage, "getItem">): ConversationalSearchResponse | null {
  try {
    const raw = storage.getItem(SEARCH_SESSION_KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (
      typeof value !== "object" || value === null ||
      !("session_id" in value) || typeof value.session_id !== "string" ||
      !("revision" in value) || !Number.isInteger(value.revision) ||
      !("results" in value) || !Array.isArray(value.results) ||
      !("active_filters" in value) || !Array.isArray(value.active_filters) ||
      !("state" in value) || typeof value.state !== "object" || value.state === null
    ) return null;
    return value as ConversationalSearchResponse;
  } catch {
    return null;
  }
}

export function saveSearch(
  storage: Pick<Storage, "setItem" | "removeItem">,
  data: ConversationalSearchResponse | null,
): void {
  if (data) storage.setItem(SEARCH_SESSION_KEY, JSON.stringify(data));
  else storage.removeItem(SEARCH_SESSION_KEY);
}
