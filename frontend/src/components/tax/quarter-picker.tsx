import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { yearOptions } from "@/lib/invoices";
import { QUARTERS, quarterEnabled, quarterHref, quarterMonths, type Quarter } from "@/lib/tax";

const ITEM = "inline-block px-4 py-2 font-semibold";

/**
 * El año (un formulario `GET`, con el trimestre en un campo oculto) y los cuatro trimestres como enlaces. Todo vive en la dirección
 * (`?year=&quarter=`) y lo lee el servidor: funciona sin JavaScript. Los trimestres que aún no han empezado no se ofrecen. Debajo del
 * trimestre, la pestaña del modelo: solo el 303 existe todavía; el 130 sale desactivado con «Próximamente», como el menú.
 */
export function QuarterPicker({ year, quarter, today }: { year: number; quarter: Quarter; today: string }) {
  const currentYear = Number(today.slice(0, 4));
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <form method="get" action="/trimestres" className="flex items-end gap-3" aria-label="Año del trimestre">
          <input type="hidden" name="quarter" value={quarter} />
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
                    href={quarterHref(year, option)}
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
          <li>
            <span aria-current="page" className={`${ITEM} bg-ink text-sheet`}>
              Modelo 303
            </span>
          </li>
          <li className="border-l border-rule-strong">
            <span aria-disabled="true" className={`${ITEM} cursor-not-allowed bg-sheet text-ink-soft`}>
              Modelo 130 <span className="ml-1 text-[13px] font-normal">Próximamente</span>
            </span>
          </li>
        </ul>
      </nav>
    </div>
  );
}
