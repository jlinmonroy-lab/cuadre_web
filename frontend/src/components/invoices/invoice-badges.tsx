import { TAG } from "@/components/scope-badge";
import { kindLabel, paymentLabel, type Invoice } from "@/lib/invoices";

/** Estado de cobro de una ordinaria, siempre escrito (el color solo refuerza). Una rectificativa no se cobra y no lleva estado. */
export function PaymentBadge({ invoice }: { invoice: Pick<Invoice, "kind" | "paid_at"> }) {
  const label = paymentLabel(invoice);
  if (label === null) return null;
  const style = invoice.paid_at ? "bg-status-ok-bg text-status-ok" : "bg-status-doubt-bg text-status-doubt";
  return <span className={`${TAG} ${style}`}>{label}</span>;
}

/** «Rectificativa» como texto con insignia; una ordinaria no lleva marca. */
export function KindBadge({ invoice }: { invoice: Pick<Invoice, "kind"> }) {
  if (invoice.kind !== "rectifying") return null;
  return <span className={`${TAG} bg-muted text-ink`}>{kindLabel(invoice.kind)}</span>;
}
