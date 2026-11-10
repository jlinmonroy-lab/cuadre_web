import Link from "next/link";

import { ScopeBadge } from "@/components/scope-badge";
import type { PreviewReply } from "@/lib/invoice-handlers";
import { conditionsText, rateText, retentionText } from "@/lib/invoices";
import { formatCents } from "@/lib/money";

/** Lo que enseña la vista previa en cada momento. */
export type PreviewView = { status: "empty" } | { status: "loading" } | { status: "failed" } | { status: "ready"; reply: PreviewReply };

const ROW = "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 border-b border-rule py-2";

/**
 * La vista previa de «Nueva factura»: lo que la API dice que se emitiría (ámbito, IVA, retención, total y mención) ANTES de emitir. La interfaz
 * no calcula nada: pinta la respuesta del servidor. Es una región `aria-live` para que el cambio se anuncie.
 */
export function InvoicePreview({ view }: { view: PreviewView }) {
  return (
    <section aria-labelledby="vista-previa" aria-live="polite" aria-busy={view.status === "loading"} className="grid gap-2 rounded-md border border-rule bg-white p-3 sm:p-4">
      <h3 id="vista-previa" className="text-[15px]">
        Vista previa
      </h3>
      <Body view={view} />
    </section>
  );
}

function Body({ view }: { view: PreviewView }) {
  if (view.status === "empty") {
    return <p className="text-sm text-ink-soft">Elige un cliente para ver qué impuestos y qué mención llevará la factura.</p>;
  }
  if (view.status === "loading") return <p className="text-sm text-ink-soft">Calculando la vista previa…</p>;
  if (view.status === "failed") return <p className="text-sm font-semibold text-status-error">No hemos podido calcular la vista previa. Puedes emitir igualmente: el servidor revisa todo.</p>;

  const { reply } = view;
  if (reply.status === "error") {
    const messages = Object.values(reply.fieldErrors);
    return (
      <div className="grid gap-1.5 text-sm text-status-error">
        {messages.length === 0 ? <p className="font-semibold">{reply.message}</p> : null}
        {messages.length > 0 ? (
          <ul className="list-disc pl-5 font-semibold">
            {messages.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        ) : null}
        {reply.missing ? (
          <ul className="list-disc pl-5">
            {reply.missing.map((item) => (
              <li key={item.field}>{item.label}</li>
            ))}
          </ul>
        ) : null}
        {reply.code === "profile_incomplete" || reply.code === "irpf_rate_missing" ? (
          <p>
            <Link href="/perfil" className="font-semibold underline underline-offset-2">
              Ir a mi perfil
            </Link>
          </p>
        ) : null}
        {reply.code === "client_not_billable" ? (
          <p>
            <Link href="/clientes" className="font-semibold underline underline-offset-2">
              Ir a Clientes
            </Link>
          </p>
        ) : null}
      </div>
    );
  }

  const { preview } = reply;
  const noVat = Number(preview.vat_rate) === 0;
  const noRetention = Number(preview.irpf_rate) === 0;
  return (
    <div className="grid gap-2">
      <dl className="text-[15px]">
        <div className={ROW}>
          <dt>Ámbito del cliente</dt>
          <dd>
            <ScopeBadge scope={preview.scope} />
          </dd>
        </div>
        {reply.base === "ok" ? (
          <>
            <div className={ROW}>
              <dt>Base imponible</dt>
              <dd className="tabular-nums">{formatCents(preview.base_cents)}</dd>
            </div>
            <div className={ROW}>
              <dt>{noVat ? "IVA" : `IVA ${rateText(preview.vat_rate)} %`}</dt>
              <dd className="tabular-nums">{noVat ? "Sin IVA" : formatCents(preview.vat_cents)}</dd>
            </div>
            <div className={ROW}>
              <dt>{noRetention ? "Retención de IRPF" : `Retención de IRPF ${rateText(preview.irpf_rate)} %`}</dt>
              <dd className="tabular-nums">{noRetention ? "No aplica" : retentionText(preview)}</dd>
            </div>
            <div className={`${ROW} border-b-0 font-bold`}>
              <dt>Total a cobrar</dt>
              <dd className="tabular-nums">{formatCents(preview.total_cents)}</dd>
            </div>
          </>
        ) : null}
      </dl>
      {reply.base !== "ok" ? (
        <>
          <p className="text-sm">{conditionsText(preview)}</p>
          <p className="text-sm text-ink-soft">
            {reply.base === "invalid"
              ? "No entendemos la base imponible: escríbela en euros, por ejemplo 1.200,00."
              : "Escribe la base imponible para ver los importes."}
          </p>
        </>
      ) : null}
      {preview.legal_note ? <p className="rounded-md bg-status-doubt-bg px-3 py-2 text-sm text-status-doubt">Mención que se añadirá a la factura: «{preview.legal_note}»</p> : null}
    </div>
  );
}
