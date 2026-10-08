import type { CatalogQuery } from "@/lib/api";
import {
  CATEGORIES,
  COLORS,
  GENDERS,
  OCCASIONS,
  SIZES,
  SORT_OPTIONS,
  STYLES,
} from "@/lib/filter-options";
import { PriceRange } from "./price-range";

export function FilterPanel({
  query,
  onChange,
}: {
  query: CatalogQuery;
  onChange: (next: CatalogQuery) => void;
}) {
  return (
    <form className="flex flex-col gap-4" onSubmit={(event) => event.preventDefault()}>
      <SelectFilter
        label="Category"
        value={query.category}
        options={CATEGORIES}
        onChange={(category) => patchQuery(query, onChange, { category })}
      />
      <SelectFilter
        label="Color"
        value={query.color}
        options={COLORS}
        onChange={(color) => patchQuery(query, onChange, { color })}
      />
      <SelectFilter
        label="Gender"
        value={query.gender}
        options={GENDERS}
        onChange={(gender) => patchQuery(query, onChange, { gender })}
      />
      <SelectFilter
        label="Occasion"
        value={query.occasion}
        options={OCCASIONS}
        onChange={(occasion) => patchQuery(query, onChange, { occasion })}
      />
      <SelectFilter
        label="Style"
        value={query.style}
        options={STYLES}
        onChange={(style) => patchQuery(query, onChange, { style })}
      />
      <SelectFilter
        label="Size"
        value={query.size}
        options={SIZES}
        onChange={(size) => patchQuery(query, onChange, { size })}
      />
      <PriceRange
        minPrice={query.min_price}
        maxPrice={query.max_price}
        onChange={(range) => patchQuery(query, onChange, range)}
      />
      <SelectFilter
        label="Sort"
        value={query.sort ?? "newest"}
        options={SORT_OPTIONS.map((option) => option.value)}
        labels={Object.fromEntries(SORT_OPTIONS.map((option) => [option.value, option.label]))}
        allowEmpty={false}
        onChange={(sort) =>
          patchQuery(query, onChange, { sort: sort as CatalogQuery["sort"] })
        }
      />
      <button
        type="button"
        onClick={() => onChange({})}
        className="rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-700"
      >
        Clear filters
      </button>
    </form>
  );
}

function patchQuery(
  query: CatalogQuery,
  onChange: (next: CatalogQuery) => void,
  patch: Partial<CatalogQuery>,
): void {
  onChange({ ...query, ...patch, page: 1 });
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
  labels,
  allowEmpty = true,
}: {
  label: string;
  value?: string;
  options: readonly string[];
  onChange: (value: string | undefined) => void;
  labels?: Record<string, string>;
  allowEmpty?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
      {label}
      <select
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || undefined)}
        className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm font-normal text-zinc-900"
      >
        {allowEmpty ? <option value="">Any</option> : null}
        {options.map((option) => (
          <option key={option} value={option}>
            {labels?.[option] ?? option}
          </option>
        ))}
      </select>
    </label>
  );
}
