import { SignInForm } from "./sign-in-form";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/lib/auth";

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ callbackUrl?: string; error?: string }> }) {
  const { callbackUrl, error } = await searchParams;
  const returnTo = typeof callbackUrl === "string" && callbackUrl.startsWith("/") && !callbackUrl.startsWith("//") && !callbackUrl.includes("\\")
    ? callbackUrl
    : "/";
  const session = await getServerSession(authOptions);
  if (session?.user?.id) redirect(returnTo);
  return <SignInForm callbackUrl={returnTo} authError={typeof error === "string" ? error : undefined} />;
}
