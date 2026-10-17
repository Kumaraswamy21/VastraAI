import { SignInForm } from "./sign-in-form";

export default async function SignInPage({ searchParams }: { searchParams: Promise<{ callbackUrl?: string }> }) {
  const { callbackUrl } = await searchParams;
  const returnTo = typeof callbackUrl === "string" && callbackUrl.startsWith("/") && !callbackUrl.startsWith("//") && !callbackUrl.includes("\\")
    ? callbackUrl
    : "/";
  return <SignInForm callbackUrl={returnTo} />;
}
