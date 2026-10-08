export function SearchPlaceholder() {
  return (
    <div className="flex min-h-full flex-1 flex-col bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <p className="text-sm font-medium tracking-wide text-zinc-500">
          AI Fashion Search
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-900">
          Describe the outfit. Review the links.
        </h1>
      </header>

      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-6 py-10">
        <p className="text-base leading-7 text-zinc-600">
          Tell the assistant what you want in plain language, for example a
          black check shirt under ₹2,000 for a wedding. It will extract filters,
          search this catalog, and return clickable product links. Off-topic
          questions are declined.
        </p>

        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-zinc-700">
            Shopping request
          </span>
          <textarea
            disabled
            rows={3}
            placeholder="Show me a black outfit for an evening wedding under ₹4,000."
            className="resize-none rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-2 text-sm text-zinc-500"
          />
        </label>

        <button
          type="button"
          disabled
          className="w-fit rounded-lg bg-zinc-300 px-4 py-2 text-sm font-medium text-zinc-500"
        >
          Search catalog
        </button>

        <p className="text-sm text-zinc-500">
          Retrieval and generation are not wired yet. Search stays disabled
          until Day 3–4.
        </p>
      </main>
    </div>
  );
}
