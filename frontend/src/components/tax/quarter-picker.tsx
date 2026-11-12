import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { yearOptions } from "@/lib/invoices";
import { OWNER_LINKS, QUARTERS, quarterEnabled, quarterMonths, type ModelKey, type Quarter, type TaxLinks } from "@/lib/tax";

const ITEM = "inline-block px-4 py-2 font-semibold";

/**
 * El año (un formulario `GET`, con el trimestre en un campo oculto) y los cuatro trimestres como enlaces. Todo vive en la dirección
 * (`?model=&year=&quarter=`) y lo lee el servidor: funciona sin JavaScript. Los trimestres que aún no han empezado no se ofrecen. Debajo del
 * trimestre, las pestañas de los dos modelos, que son enlaces y conservan el año y el trimestre. El 303 no lleva `model` en la dirección.
 */
export function QuarterPicker({
  year,
  quarter,
  model,
  today,
  links = OWNER_LINKS,
  formAction = "/trimestres",
  hidden = {},
}: {
  year: number;
  quarter: Quarter;
  model: ModelKey;
  today: string;
  /** Las direcciones de los trimestres y de los modelos (por defecto, las del autónomo). */
  links?: Pick<TaxLinks, "quarter">;
  /** A dónde va el formulario del año y qué campos fijos lleva (en la ficha del gestor, su ruta y `tab=trimestres`). */
  formAction?: string;
  hidden?: Record<string, string>;
}) {
  const currentYear = Number(today.slice(0, 4));
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <form method="get" action={formAction} className="flex items-end gap-3" aria-label="Año del trimestre">
          {Object.entries(hidden).map(([name, value]) => (
            <input key={name} type="hidden" name={name} value={value} />
          ))}
          <input type="hidden" name="quarter" value={quarter} />
          {model === "130" ? <input type="hidden" name="model" value="130" /> : null}
          <div className="grid gap-1.5">
            <Label htmlFor="trimestre-year" className="text-[13px] font-semibold text-ink-soft">
              Año
            </Label>
            <NativeSelect id="trimestre-year" name="year" defaultValue={String(year)} className="w-28">
              {yearOptions(currentYear, year).map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </NativeSelect>
          </div>
          <Button type="submit" variant="outline">
            Ver
          </Button>
        </form>
        <nav aria-label="Trimestre">
          <ul className="m-0 flex w-max list-none overflow-hidden rounded-lg border border-rule-strong p-0">
            {QUARTERS.map((option) => {
              const selected = option === quarter;
              const border = option === 1 ? "" : "border-l border-rule-strong";
              if (!quarterEnabled(year, option, today)) {
                return (
                  <li key={option} className={border}>
                    <span aria-disabled="true" className={`${ITEM} cursor-not-allowed bg-sheet text-ink-soft opacity-60`}>
                      T{option}
                      <span className="sr-only"> (todavía no ha empezado)</span>
                    </span>
                  </li>
                );
              }
              return (
                <li key={option} className={border}>
                  <Link
                    href={links.quarter(year, option, model)}
                    aria-current={selected ? "page" : undefined}
                    title={quarterMonths(option)}
                    className={`${ITEM} ${selected ? "bg-ink text-sheet" : "bg-sheet text-ink hover:bg-paper"}`}
                  >
                    T{option}
                    <span className="sr-only">, {quarterMonths(option)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
      <nav aria-label="Modelo">
        <ul className="m-0 flex w-max list-none overflow-hidden rounded-lg border border-rule-strong p-0">
          {(["303", "130"] as const).map((option) => {
            const selected = option === model;
            return (
              <li key={option} className={option === "303" ? "" : "border-l border-rule-strong"}>
                <Link
                  href={links.quarter(year, quarter, option)}
                  aria-current={selected ? "page" : undefined}
                  className={`${ITEM} ${selected ? "bg-ink text-sheet" : "bg-sheet text-ink hover:bg-paper"}`}
                >
                  Modelo {option}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
