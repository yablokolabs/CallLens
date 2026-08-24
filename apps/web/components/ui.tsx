import type { ReactNode } from "react";
import { cx } from "@/lib/utils";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-2xl border border-zinc-800 bg-zinc-900/50 p-5", className)}>
      {children}
    </div>
  );
}

export function SectionTitle({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{children}</h2>
      {sub ? <p className="mt-1 text-sm text-zinc-500">{sub}</p> : null}
    </div>
  );
}

export function Badge({
  children,
  tone = "zinc",
}: {
  children: ReactNode;
  tone?: "zinc" | "emerald" | "amber" | "rose" | "indigo";
}) {
  const tones: Record<string, string> = {
    zinc: "border-zinc-700 bg-zinc-800/60 text-zinc-300",
    emerald: "border-emerald-700/50 bg-emerald-900/30 text-emerald-300",
    amber: "border-amber-700/50 bg-amber-900/30 text-amber-300",
    rose: "border-rose-700/50 bg-rose-900/30 text-rose-300",
    indigo: "border-indigo-700/50 bg-indigo-900/30 text-indigo-300",
  };
  return (
    <span className={cx("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <Card>
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
      {sub ? <div className="mt-1 text-xs text-zinc-500">{sub}</div> : null}
    </Card>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-800 py-16 text-center">
      <div className="text-sm font-medium text-zinc-300">{title}</div>
      <p className="mt-1 max-w-md text-sm text-zinc-500">{body}</p>
    </div>
  );
}
