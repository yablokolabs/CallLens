"use client";

import { useState } from "react";
import Link from "next/link";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center">
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-xl font-bold">
          CL
        </div>
        <h1 className="text-xl font-semibold">Sign in to CallLens</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Self-hosted — authentication is reserved for the Supabase integration. For local use, head to the dashboard.
        </p>
      </div>
      <form
        className="space-y-3 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6"
        onSubmit={(e) => e.preventDefault()}
      >
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled
          className="w-full rounded-xl bg-zinc-800 py-2 text-sm font-medium text-zinc-500"
          title="Auth lands with the Supabase integration"
        >
          Sign in (coming soon)
        </button>
        <p className="text-center text-xs text-zinc-600">
          Just exploring?{" "}
          <Link href="/dashboard" className="text-indigo-400 hover:text-indigo-300">
            Open the dashboard
          </Link>
          .
        </p>
      </form>
    </div>
  );
}
