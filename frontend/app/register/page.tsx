import { RegisterForm } from "./register-form";

export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ callbackUrl?: string }> }) {
  const { callbackUrl } = await searchParams;
  const returnTo = typeof callbackUrl === "string" && callbackUrl.startsWith("/") && !callbackUrl.startsWith("//") && !callbackUrl.includes("\\")
    ? callbackUrl
    : "/";
  return <RegisterForm callbackUrl={returnTo} />;
}
