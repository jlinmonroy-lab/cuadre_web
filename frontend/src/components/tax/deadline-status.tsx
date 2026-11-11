import { TAG } from "@/components/scope-badge";
import { deadlineBanner, type Banner, type Modelo130, type Modelo303 } from "@/lib/tax";

const TONE: Record<Banner["tone"], string> = {
  neutral: "bg-muted text-ink",
  doubt: "bg-status-doubt-bg text-status-doubt",
  ok: "bg-status-ok-bg text-status-ok",
};

/** El estado del plazo del trimestre, siempre escrito (el color solo refuerza) y con la fecha que manda el servidor. */
export function DeadlineStatus({ model }: { model: Pick<Modelo303 | Modelo130, "deadline_status" | "deadline"> }) {
  const banner = deadlineBanner(model);
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className={`${TAG} ${TONE[banner.tone]}`}>{banner.label}</span>
      <span>{banner.text}</span>
    </p>
  );
}
