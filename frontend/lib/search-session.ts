import type { ConversationalSearchResponse } from "./api";

export const SEARCH_SESSION_KEY = "vastraai-search-v1";
export function searchSessionKey(userId: string): string { return `${SEARCH_SESSION_KEY}:${userId}`; }

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  productIds?: number[];
};

export type SearchSnapshot = {
  data: ConversationalSearchResponse;
  messages: ConversationMessage[];
};

export function restoreSearch(storage: Pick<Storage, "getItem">, key = SEARCH_SESSION_KEY): ConversationalSearchResponse | null {
  try {
    const raw = storage.getItem(key);
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
  key = SEARCH_SESSION_KEY,
): void {
  if (data) storage.setItem(key, JSON.stringify(data));
  else storage.removeItem(key);
}

export function restoreSnapshot(storage: Pick<Storage, "getItem">, key = SEARCH_SESSION_KEY): SearchSnapshot | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || !("data" in value) || !("messages" in value)) {
      const legacy = restoreSearch(storage, key);
      return legacy ? { data: legacy, messages: [] } : null;
    }
    const snapshot = value as SearchSnapshot;
    if (!snapshot.data || !Array.isArray(snapshot.messages) || !snapshot.messages.every((message) =>
      typeof message.id === "string" && (message.role === "user" || message.role === "assistant") && typeof message.content === "string" && (message.productIds === undefined || (Array.isArray(message.productIds) && message.productIds.every((id) => Number.isInteger(id))) )
    )) return null;
    return snapshot;
  } catch {
    return null;
  }
}

export function saveSnapshot(
  storage: Pick<Storage, "setItem" | "removeItem">,
  data: ConversationalSearchResponse | null,
  messages: ConversationMessage[],
  key = SEARCH_SESSION_KEY,
): void {
  if (data) storage.setItem(key, JSON.stringify({ data, messages }));
  else storage.removeItem(key);
}
