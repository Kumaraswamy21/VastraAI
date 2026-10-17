import { ObservabilityDashboard } from "./observability-dashboard";
import { getServerSession } from "next-auth";
import { notFound } from "next/navigation";
import { authOptions } from "@/lib/auth";

export default async function ObservabilityPage() {
  const session = await getServerSession(authOptions);
  const allowlist = (process.env.AUTH_ADMIN_EMAILS ?? "").split(",").map(email => email.trim().toLowerCase());
  if (!session?.user?.email || !allowlist.includes(session.user.email.toLowerCase())) notFound();
  return <ObservabilityDashboard />;
}
