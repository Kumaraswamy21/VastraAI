"use client";

import { useState } from "react";
import Link from "next/link";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const response = await fetch("/api/backend/auth/password-reset/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      setMessage(response.ok ? "If this email has an eligible account, a reset link will arrive shortly." : "Password reset is temporarily unavailable.");
    } catch { setMessage("Password reset is temporarily unavailable."); }
  }
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12"><h1 className="font-serif text-4xl">Reset password</h1><form onSubmit={submit} className="mt-8 space-y-4"><label className="block text-sm">Email<input type="email" required value={email} onChange={e => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border p-3" /></label><button className="w-full rounded-xl bg-stone-900 p-3 text-white">Send reset link</button></form>{message && <p role="status" className="mt-4 text-sm">{message}</p>}<Link href="/sign-in" className="mt-6 underline">Back to sign in</Link></main>;
}
