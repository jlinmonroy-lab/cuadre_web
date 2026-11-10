import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { SCOPE_LABEL, SCOPES, yearOptions, type ListQuery } from "@/lib/invoices";

const paidValue = (paid: boolean | undefined) => (paid === undefined ? "" : paid ? "paid" : "unpaid");

/**
 * Año, ámbito y cobro de la lista. Es un formulario `GET` normal: funciona sin JavaScript, el filtro vive en la dirección (`?year=&scope=&paid=`)
 * y la lista la lee el servidor. Los nombres de campo son los de la dirección.
 */
export function InvoiceFilters({ query, currentYear }: { query: ListQuery; currentYear: number }) {
  return (
    <form method="get" action="/facturas" className="flex flex-wrap items-end gap-3" aria-label="Filtros de la lista de facturas">
      <div className="grid gap-1.5">
        <Label htmlFor="filtro-year" className="text-[13px] font-semibold text-ink-soft">
          Año
        </Label>
        <NativeSelect id="filtro-year" name="year" defaultValue={String(query.year)} className="w-28">
          {yearOptions(currentYear, query.year).map((year) => (
            <option key={year} value={year}>
              {year}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="filtro-scope" className="text-[13px] font-semibold text-ink-soft">
          Ámbito
        </Label>
        <NativeSelect id="filtro-scope" name="scope" defaultValue={query.scope ?? ""} className="w-44">
          <option value="">Todos</option>
          {SCOPES.map((scope) => (
            <option key={scope} value={scope}>
              {SCOPE_LABEL[scope]}
            </option>
          ))}
        </NativeSelect>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor="filtro-paid" className="text-[13px] font-semibold text-ink-soft">
          Cobro
        </Label>
        <NativeSelect id="filtro-paid" name="paid" defaultValue={paidValue(query.paid)} className="w-40">
          <option value="">Todas</option>
          <option value="unpaid">Pendientes</option>
          <option value="paid">Cobradas</option>
        </NativeSelect>
      </div>
      <Button type="submit" variant="outline">
        Aplicar filtros
      </Button>
    </form>
  );
}
