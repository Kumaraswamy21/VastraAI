import assert from "node:assert/strict";
import test from "node:test";
import { restoreSearch, saveSearch, SEARCH_SESSION_KEY } from "../lib/search-session.ts";

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

test("search session survives storage round trip", () => {
  const store = storage();
  const response = {
    session_id: "session-1", revision: 2, results: [], active_filters: [], state: {},
  };
  saveSearch(store, response);
  assert.equal(store.getItem(SEARCH_SESSION_KEY) !== null, true);
  assert.deepEqual(restoreSearch(store), response);
  saveSearch(store, null);
  assert.equal(restoreSearch(store), null);
});

test("invalid or partial storage cannot restore a session", () => {
  const store = storage();
  store.setItem(SEARCH_SESSION_KEY, "{bad json");
  assert.equal(restoreSearch(store), null);
  store.setItem(SEARCH_SESSION_KEY, JSON.stringify({session_id: "x", revision: 1}));
  assert.equal(restoreSearch(store), null);
});
