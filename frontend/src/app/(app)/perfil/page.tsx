import type { Metadata } from "next";

import { LogoPanel } from "@/components/profile/logo-panel";
import { ProfileForm } from "@/components/profile/profile-form";
import { RemindersSection } from "@/components/profile/reminders-section";
import { SeriesSection } from "@/components/profile/series-section";
import { getProfile, listInvoiceSeries } from "@/lib/profile-api";
import { valuesFromProfile } from "@/lib/profile-form";
import { getReminderSettings } from "@/lib/reminders-api";
import { requireRole } from "@/lib/session";

// Depende de la sesión en cada navegación (ver el layout de (app)): no es «instantánea» y no se valida como tal.
export const instant = false;

export const metadata: Metadata = { title: "Perfil" };

export default async function PerfilPage() {
  await requireRole("usuario"); // el gestor y el administrador van a /403; la API vuelve a decidirlo
  const [profile, series, reminders] = await Promise.all([getProfile(), listInvoiceSeries(), getReminderSettings()]);
  const { can_issue: canIssue, missing_for_invoicing: missing } = profile.completeness;

  return (
    <>
      <header className="mb-6">
        <h1>Perfil</h1>
        <p className="mt-1 max-w-[70ch] text-ink-soft">
          Tus datos fiscales y los de tu negocio. Los rellenas una vez y la aplicación los usa en tus facturas y en la deducibilidad de tus gastos.
        </p>
      </header>
      <div className="grid gap-8">
        <p
          role="status"
          className={`rounded-md border px-3 py-2.5 text-sm font-semibold ${canIssue ? "border-status-ok bg-status-ok-bg text-status-ok" : "border-status-doubt-line bg-status-doubt-bg text-status-doubt"}`}
        >
          {canIssue ? "Tu perfil está listo para emitir facturas." : `Para emitir facturas te falta: ${missing.map((item) => item.label).join(", ")}.`}
        </p>
        <ProfileForm initial={valuesFromProfile(profile)} retention={profile.retention} />
        <RemindersSection initial={reminders} />
        <section aria-labelledby="logo-titulo" className="grid gap-3 rounded-panel border border-rule bg-sheet p-4 sm:p-5">
          <h2 id="logo-titulo">Logo</h2>
          <LogoPanel hasLogo={profile.has_logo} />
        </section>
        <section aria-labelledby="series-titulo" className="grid gap-3">
          <h2 id="series-titulo">Series de facturación</h2>
          <p className="max-w-[70ch] text-[13px] text-ink-soft">
            La serie del año se crea sola al guardar tu perfil. Puedes añadir otras, elegir la predeterminada, archivar las que no uses y fijar el
            número inicial mientras no hayas emitido ninguna factura en ella.
          </p>
          <SeriesSection series={series} />
        </section>
      </div>
    </>
  );
}
