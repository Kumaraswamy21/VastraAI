import { HealthStatus } from "./health-status";
import { SearchView } from "./search-view";
import { PublicSearchLanding } from "./public-search-landing";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export default async function Home({ searchParams }: { searchParams: Promise<{ query?: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) return <PublicSearchLanding />;
  const { query } = await searchParams;
  return (
    <>
      <HealthStatus />
      <SearchView userId={session.user.id} initialQuery={typeof query === "string" ? query.slice(0, 300) : ""} />
    </>
  );
}
