import { TAG } from "@/components/scope-badge";
import { statusLabel, type MonthStatus } from "@/lib/monthly";

const TONE: Record<MonthStatus, string> = {
  closed: "bg-status-ok-bg text-status-ok",
  in_progress: "bg-muted text-ink",
  pending: "bg-status-doubt-bg text-status-doubt",
};

/** El estado del mes, siempre escrito (el color solo refuerza). */
export function MonthStatusBadge({ status }: { status: MonthStatus }) {
  return <span className={`${TAG} ${TONE[status]}`}>{statusLabel(status)}</span>;
}
