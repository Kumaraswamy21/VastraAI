"use client";

import { useState } from "react";
import Link from "next/link";

export function RegisterForm({ callbackUrl }: { callbackUrl: string }) {
  const signInHref = `/sign-in?${new URLSearchParams({ callbackUrl })}`;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/backend/auth/register", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
      setMessage(response.ok ? "Check your email for a verification link." : "Registration is unavailable. Please try again.");
    } catch { setMessage("Registration is unavailable. Please try again."); }
    finally { setBusy(false); }
  }
  async function resend() {
    if (!email) { setMessage("Enter your email address first."); return; }
    try {
      const response = await fetch("/api/backend/auth/verification/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      setMessage(response.ok ? "If this address needs verification, another email will arrive shortly." : "Verification email is temporarily unavailable.");
    } catch { setMessage("Verification email is temporarily unavailable."); }
  }
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12 text-stone-900">
    <Link href="/" className="mb-8 font-serif text-2xl">VastraAI</Link>
    <h1 className="font-serif text-4xl">Create an account</h1>
    <form onSubmit={submit} className="mt-8 space-y-4">
      <label className="block text-sm">Email<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 p-3" /></label>
      <label className="block text-sm">Password (12 characters or more)<input type="password" autoComplete="new-password" minLength={12} required value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-stone-300 p-3" /></label>
      {message && <p role="status" className="text-sm">{message}</p>}
      <button disabled={busy} className="w-full rounded-xl bg-stone-900 p-3 font-medium text-white disabled:opacity-50">Create account</button>
    </form>
    <button type="button" onClick={resend} className="mt-5 text-left text-sm underline">Resend verification email</button>
    <Link href={signInHref} className="mt-5 text-sm underline">Already have an account? Sign in</Link>
  </main>;
}
