"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";

function GoogleLogo() {
  return <svg aria-hidden="true" viewBox="0 0 48 48" className="size-5 shrink-0">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.39 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5Z" />
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.28 5.48-4.81 7.18l7.73 6C44.36 38.03 46.98 31.89 46.98 24.55Z" />
    <path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.2A23.9 23.9 0 0 0 0 24c0 3.87.93 7.51 2.56 10.78l7.97-6.19Z" />
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.91-5.8l-7.73-6C30.03 37.65 27.29 38.5 24 38.5c-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48Z" />
  </svg>;
}

export function SignInForm({ callbackUrl, authError }: { callbackUrl: string; authError?: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await signIn("credentials", { email, password, redirect: false, callbackUrl });
      if (result?.error) {
        setError("Sign-in failed. Check your credentials and verify your email.");
      } else {
        window.location.assign(result?.url ?? callbackUrl);
      }
    } catch {
      setError("Sign-in is temporarily unavailable.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12 text-stone-900">
    <Link href="/catalog" className="mb-8 font-serif text-2xl">VastraAI</Link>
    <h1 className="font-serif text-4xl">Sign in to search</h1>
    <p className="mt-2 text-sm text-stone-600">Your search preferences stay with your account.</p>
    {authError && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">Sign-in could not be completed. Please try again. If this continues, check the Google OAuth and backend settings.</p>}
    <button type="button" onClick={() => signIn("google", { callbackUrl })} className="mt-8 flex items-center justify-center gap-3 rounded-xl border border-stone-300 bg-white px-4 py-3 font-medium transition hover:border-stone-500"><GoogleLogo />Continue with Google</button>
    <div className="my-6 text-center text-xs uppercase tracking-widest text-stone-500">or use email</div>
    <form onSubmit={submit} className="space-y-4">
      <label className="block text-sm">Email<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 p-3" /></label>
      <label className="block text-sm">Password<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 p-3" /></label>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <button disabled={busy} className="w-full rounded-xl bg-stone-900 p-3 font-medium text-white disabled:opacity-50">{busy ? "Signing in…" : "Sign in"}</button>
    </form>
    <div className="mt-5 flex justify-between text-sm"><Link href={`/register?${new URLSearchParams({ callbackUrl })}`} className="underline">Create account</Link><Link href="/forgot-password" className="underline">Forgot password?</Link></div>
  </main>;
}
