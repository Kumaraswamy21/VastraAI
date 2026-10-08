import { Suspense } from "react";
import { CatalogView } from "./catalog-view";

export default function CatalogPage() {
  return (
    <Suspense fallback={<p className="p-8 text-sm text-zinc-500">Loading catalog…</p>}>
      <CatalogView />
    </Suspense>
  );
}
