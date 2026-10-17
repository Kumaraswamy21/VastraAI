"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense } from "react";

function VerifyContent() {
  const token = useSearchParams().get("token");
  const [message, setMessage] = useState("Verifying your email…");
  useEffect(() => {
    if (!token) return;
    fetch("/api/backend/auth/verify-email", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) })
      .then(response => setMessage(response.ok ? "Email verified. You can sign in now." : "Verification link is invalid or expired."))
      .catch(() => setMessage("Verification is temporarily unavailable."));
  }, [token]);
  return <p role="status" className="mt-5 text-stone-700">{token ? message : "Verification link is missing."}</p>;
}

export default function VerifyEmailPage() {
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-12"><h1 className="font-serif text-4xl">Verify email</h1><Suspense fallback={<p>Loading…</p>}><VerifyContent /></Suspense><Link href="/sign-in" className="mt-6 underline">Go to sign in</Link></main>;
}
