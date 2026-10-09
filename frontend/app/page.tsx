import { HealthStatus } from "./health-status";
import { SearchView } from "./search-view";

export default function Home() {
  return (
    <>
      <HealthStatus />
      <SearchView />
    </>
  );
}
