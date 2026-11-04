import type { ReactNode } from "react";

import type { Notice } from "@/lib/notices";

const TONES: Record<Notice["tone"], string> = {
  info: "border-rule-strong bg-muted text-ink",
  success: "border-status-ok bg-status-ok-bg text-status-ok",
  error: "border-status-error bg-status-error-bg text-status-error",
};

/** Aviso de la URL (`?aviso=`): el texto sale de una lista cerrada (lib/notices.ts), nunca de la URL. */
export function NoticeBox({ notice }: { notice: Notice | null }) {
  if (!notice) return null;
  return (
    <p role={notice.tone === "error" ? "alert" : "status"} className={`rounded-md border px-3 py-2.5 text-sm font-semibold ${TONES[notice.tone]}`}>
      {notice.text}
    </p>
  );
}

export function AuthCard({ title, lead, children }: { title: string; lead?: string; children: ReactNode }) {
  return (
    <section aria-labelledby="auth-title" className="grid gap-5 rounded-panel border border-rule bg-sheet p-6 sm:p-8">
      <div className="grid gap-1.5">
        <h1 id="auth-title">{title}</h1>
        {lead ? <p className="text-ink-soft">{lead}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function AuthCardSkeleton() {
  return (
    <div aria-hidden="true" className="grid gap-4 rounded-panel border border-rule bg-sheet p-6 sm:p-8">
      <div className="h-8 w-2/3 rounded bg-muted" />
      <div className="h-10 rounded bg-muted" />
      <div className="h-10 rounded bg-muted" />
      <div className="h-10 rounded bg-muted" />
    </div>
  );
}
