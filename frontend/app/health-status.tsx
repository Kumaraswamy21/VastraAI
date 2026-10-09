"use client";

import { useEffect, useState } from "react";
import { fetchHealth, isHealthy, type HealthPayload } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; health: HealthPayload };

function StatusPill({ label, value }: { label: string; value: string }) {
  const ok = isHealthy(value);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
        ok ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-800"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`}
        aria-hidden
      />
      {label}: {ok ? "ok" : "error"}
    </span>
  );
}

export function HealthStatus() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchHealth()
      .then((health) => {
        if (!cancelled) setState({ kind: "ready", health });
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Health request failed";
        if (!cancelled) setState({ kind: "error", message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="border-b border-zinc-200 bg-white px-6 py-3">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
        Stack health
      </p>
      <HealthBody state={state} />
    </div>
  );
}

function HealthBody({ state }: { state: LoadState }) {
  if (state.kind === "loading") {
    return <p className="mt-1 text-sm text-zinc-500">Checking backend and database…</p>;
  }
  if (state.kind === "error") {
    return (
      <p className="mt-1 text-sm text-red-700">
        Backend: error. Database: unknown. {state.message}
      </p>
    );
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      <StatusPill label="Backend" value={state.health.backend} />
      <StatusPill label="Database" value={state.health.database} />
    </div>
  );
}
