import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { yearOptions } from "@/lib/invoices";

/**
 * El año de la contabilidad mensual: un formulario `GET` (`?anio=`) que lee el servidor, así que funciona sin JavaScript. Al cambiar de año no se conserva el
 * mes: el servidor enseña el último cerrado de ese año.
 */
export function YearPicker({ year, today }: { year: number; today: string }) {
  const currentYear = Number(today.slice(0, 4));
  return (
    <form method="get" action="/mensual" className="flex items-end gap-3" aria-label="Año de la contabilidad mensual">
      <div className="grid gap-1.5">
        <Label htmlFor="mensual-anio" className="text-[13px] font-semibold text-ink-soft">
          Año
        </Label>
        <NativeSelect id="mensual-anio" name="anio" defaultValue={String(year)} className="w-28">
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
  );
}
