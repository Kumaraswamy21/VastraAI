export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  const previous = page > 1;
  const next = page < totalPages;
  return (
    <nav className="flex items-center justify-center gap-3 pt-6" aria-label="Pagination">
      <button
        type="button"
        disabled={!previous}
        onClick={() => onPage(page - 1)}
        className="rounded-md border border-zinc-200 px-3 py-1.5 text-sm disabled:opacity-40"
      >
        Previous
      </button>
      <p className="text-sm text-zinc-600">
        Page {page} of {totalPages}
      </p>
      <button
        type="button"
        disabled={!next}
        onClick={() => onPage(page + 1)}
        className="rounded-md border border-zinc-200 px-3 py-1.5 text-sm disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}
