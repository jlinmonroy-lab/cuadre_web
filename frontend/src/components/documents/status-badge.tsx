import { CircleAlert, CircleCheck, Clock, LoaderCircle, TriangleAlert } from "lucide-react";

import { statusView, type DocumentStatus, type Tone } from "@/lib/documents";

const TONES: Record<Tone, string> = {
  ok: "bg-status-ok-bg text-status-ok",
  doubt: "bg-status-doubt-bg text-status-doubt",
  error: "bg-status-error-bg text-status-error",
  neutral: "bg-muted text-ink-soft",
};

function StatusIcon({ status, tone }: { status: DocumentStatus; tone: Tone }) {
  const className = "size-3.5 shrink-0";
  if (status === "processing") return <LoaderCircle aria-hidden="true" className={`${className} animate-spin motion-reduce:animate-none`} />;
  if (tone === "doubt") return <TriangleAlert aria-hidden="true" className={className} />;
  if (tone === "error") return <CircleAlert aria-hidden="true" className={className} />;
  if (tone === "ok") return <CircleCheck aria-hidden="true" className={className} />;
  return <Clock aria-hidden="true" className={className} />;
}

/** Estado de un documento: icono + texto + color. El color nunca va solo (T2-11). */
export function StatusBadge({ status, doubtfulCount = 0 }: { status: DocumentStatus; doubtfulCount?: number }) {
  const view = statusView(status, doubtfulCount);
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[13px] font-semibold ${TONES[view.tone]}`}>
      <StatusIcon status={status} tone={view.tone} />
      <span>{view.label}</span>
      {view.detail ? <span className="font-medium">· {view.detail}</span> : null}
    </span>
  );
}
