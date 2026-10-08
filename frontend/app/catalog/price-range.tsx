export function PriceRange({
  minPrice,
  maxPrice,
  onChange,
}: {
  minPrice?: number;
  maxPrice?: number;
  onChange: (range: { min_price?: number; max_price?: number }) => void;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium text-zinc-700">Price (INR)</legend>
      <div className="flex gap-2">
        <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-500">
          Min
          <input
            type="number"
            min={0}
            value={minPrice ?? ""}
            onChange={(event) =>
              onChange({ min_price: parsePrice(event.target.value), max_price: maxPrice })
            }
            className="rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900"
          />
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs text-zinc-500">
          Max
          <input
            type="number"
            min={0}
            value={maxPrice ?? ""}
            onChange={(event) =>
              onChange({ min_price: minPrice, max_price: parsePrice(event.target.value) })
            }
            className="rounded-md border border-zinc-200 px-2 py-1.5 text-sm text-zinc-900"
          />
        </label>
      </div>
    </fieldset>
  );
}

function parsePrice(value: string): number | undefined {
  if (value === "") return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return undefined;
  return Math.trunc(parsed);
}
