import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CallLens — Conversation Intelligence",
  description:
    "Open-source conversation intelligence and behavioral evaluation powered by LangGraph. Every semantic score is evidence-backed.",
};

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/calls", label: "Calls" },
  { href: "/reps", label: "Representatives" },
  { href: "/rubrics", label: "Rubrics" },
  { href: "/analytics", label: "Analytics" },
  { href: "/evaluations", label: "Evaluations" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} bg-zinc-950 text-zinc-100 antialiased`}>
        <div className="flex min-h-screen">
          <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-zinc-800 bg-zinc-950 px-4 py-6 md:flex">
            <Link href="/dashboard" className="mb-8 flex items-center gap-2 px-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-sm font-bold">
                CL
              </span>
              <span className="text-lg font-semibold tracking-tight">CallLens</span>
            </Link>
            <nav className="flex flex-col gap-1">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-lg px-3 py-2 text-sm text-zinc-400 transition hover:bg-zinc-900 hover:text-zinc-100"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
            <div className="mt-auto rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-xs text-zinc-500">
              Every semantic score is backed by timestamped evidence you can click to play.
            </div>
          </aside>
          <main className="flex-1 px-6 py-6 md:ml-60 md:px-10">{children}</main>
        </div>
      </body>
    </html>
  );
}
