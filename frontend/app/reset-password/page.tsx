"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

function ResetContent() {
  const token = useSearchParams().get("token");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token) { setMessage("Reset link is missing."); return; }
    try {
      const response = await fetch("/api/backend/auth/password-reset/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, password }) });
      setMessage(response.ok ? "Password updated. You can sign in now." : "Reset link is invalid or expired.");
    } catch { setMessage("Password reset is temporarily unavailable."); }
  }
  return <><form onSubmit={submit} className="mt-8 space-y-4"><label className="block text-sm">New password (12 characters or more)<input type="password" minLength={12} required autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border p-3" /></label><button className="w-full rounded-xl bg-stone-900 p-3 text-white">Update password</button></form>{message && <p role="status" className="mt-4 text-sm">{message}</p>}</>;
}

export default function ResetPasswordPage() {
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12"><h1 className="font-serif text-4xl">Choose a new password</h1><Suspense fallback={<p>Loading…</p>}><ResetContent /></Suspense><Link href="/sign-in" className="mt-6 underline">Back to sign in</Link></main>;
}
