"use client";

import { useState, type ReactNode } from "react";

export function FilterDrawer({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="mb-4 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm md:hidden"
        onClick={() => setOpen(true)}
      >
        Filters
      </button>
      {open ? (
        <button
          type="button"
          aria-label="Close filters"
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setOpen(false)}
        />
      ) : null}
      <aside
        className={`z-50 w-72 shrink-0 overflow-y-auto bg-white p-4 shadow-lg md:static md:z-auto md:block md:w-64 md:p-0 md:shadow-none ${
          open ? "fixed inset-y-0 left-0" : "hidden md:block"
        }`}
      >
        <div className="mb-4 flex items-center justify-between md:hidden">
          <p className="text-sm font-semibold">Filters</p>
          <button type="button" className="text-sm text-zinc-600" onClick={() => setOpen(false)}>
            Close
          </button>
        </div>
        {children}
      </aside>
    </>
  );
}
