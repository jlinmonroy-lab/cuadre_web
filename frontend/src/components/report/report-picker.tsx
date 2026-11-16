import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { yearOptions } from "@/lib/invoices";
import { MONTH_OPTIONS } from "@/lib/report";

/** El año y el mes del reporte: un formulario `GET` (`?anio=&mes=`) que lee el servidor, así que funciona sin JavaScript. */
export function ReportPicker({ year, month, today }: { year: number; month: number | null; today: string }) {
  const currentYear = Number(today.slice(0, 4));
  return (
    <form method="get" action="/reporte" className="flex flex-wrap items-end gap-3" aria-label="Mes del reporte">
      <div className="grid gap-1.5">
        <Label htmlFor="reporte-mes" className="text-[13px] font-semibold text-ink-soft">
          Mes
        </Label>
        <NativeSelect id="reporte-mes" name="mes" defaultValue={month === null ? undefined : String(month)} className="w-40">
          {MONTH_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="reporte-anio" className="text-[13px] font-semibold text-ink-soft">
          Año
        </Label>
        <NativeSelect id="reporte-anio" name="anio" defaultValue={String(year)} className="w-28">
          {yearOptions(currentYear, year).map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </NativeSelect>
      </div>
      <Button type="submit" variant="outline">
        Ver reporte
      </Button>
    </form>
  );
}
