import { TAG } from "@/components/scope-badge";
import { formatDate, rateText } from "@/lib/invoices";
import type { OwnerProfileView } from "@/lib/gestor-reads-api";

const dash = (value: string | null | undefined): string => (value && value.trim() !== "" ? value : "—");
const percent = (value: string | null): string => (value === null ? "—" : `${rateText(value)} %`);
const irpf = (rate: OwnerProfileView["profile"]["irpf_rate"]): string => (rate === "7.00" ? "7 % (reducida)" : rate === "15.00" ? "15 %" : "—");

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid content-start gap-0.5">
      <dt className="text-[13px] font-semibold text-ink-soft">{label}</dt>
      <dd className="m-0 [overflow-wrap:anywhere]">{value}</dd>
    </div>
  );
}

/** El perfil del negocio de un autónomo, en lectura. El IBAN se enseña tal cual (P-01). Todo se pinta como texto. */
export function OwnerProfile({ view }: { view: OwnerProfileView }) {
  const { profile, series } = view;
  return (
    <div className="grid gap-6">
      <section aria-labelledby="perfil-negocio" className="grid gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
        <h2 id="perfil-negocio" className="text-base">
          Perfil del negocio
        </h2>
        <dl className="m-0 grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <Field label="Nombre o razón social" value={dash(profile.legal_name)} />
          <Field label="NIF" value={dash(profile.tax_id)} />
          <Field label="Domicilio fiscal" value={dash(profile.fiscal_address)} />
          <Field label="Actividad" value={dash(profile.activity)} />
          <Field label="Epígrafe del IAE" value={dash(profile.iae_epigraph)} />
          <Field label="Fecha de alta" value={profile.activity_start_date ? formatDate(profile.activity_start_date) : "—"} />
          <Field label="Régimen de IVA" value="General" />
          <Field label="Retención de IRPF" value={irpf(profile.irpf_rate)} />
          <Field label="Porcentaje de vivienda afecta" value={percent(profile.home_pct)} />
          <Field label="IBAN" value={dash(profile.iban)} />
        </dl>
      </section>
      <section aria-labelledby="perfil-series" className="grid gap-3">
        <h2 id="perfil-series" className="text-base">
          Series de facturación
        </h2>
        {series.length === 0 ? (
          <p className="text-ink-soft">Todavía no tiene series.</p>
        ) : (
          <ul className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr))]">
            {series.map((item) => (
              <li key={item.id} className="grid content-start gap-1.5 rounded-panel border border-rule bg-sheet p-4">
                <h3 className="text-[15px] leading-snug">Serie {item.code}</h3>
                {item.description ? <p className="text-[13px] text-ink-soft [overflow-wrap:anywhere]">{item.description}</p> : null}
                <p className="text-[13px] text-ink-soft">
                  Siguiente número: <span className="font-semibold tabular-nums text-ink">{item.next_number}</span>
                </p>
                {item.is_default || item.archived || item.in_use ? (
                  <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Marcas de la serie">
                    {item.is_default ? <li className={`${TAG} bg-action-soft text-action-hover`}>Predeterminada</li> : null}
                    {item.archived ? <li className={`${TAG} bg-muted text-ink-soft`}>Archivada</li> : null}
                    {item.in_use ? <li className={`${TAG} bg-scope-eu-bg text-scope-eu`}>En uso</li> : null}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
