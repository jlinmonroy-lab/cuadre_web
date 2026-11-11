import { BoxLine } from "@/components/tax/box-row";
import { boxView130, groupBoxes130, quarterTitle, resultText130, withheldShareText, type Modelo130, type Quarter } from "@/lib/tax";

/**
 * La hoja del modelo 130 como el prototipo: cabecera oscura, las casillas agrupadas y el resultado al pie, con el porcentaje de ingresos con retención como
 * información. Todo lo que enseña lo calculó el servidor; aquí solo se ordena y se escribe. Es un borrador orientativo, acumulado desde el 1 de enero: no hay
 * botón de presentar.
 */
export function Modelo130Sheet({ model }: { model: Modelo130 }) {
  const groups = groupBoxes130(model.boxes);
  const title = quarterTitle(model.year, model.quarter as Quarter);
  const share = withheldShareText(model.withheld_share_percent);
  return (
    <section aria-labelledby="modelo-130" className="max-w-3xl border border-ink bg-sheet">
      <header className="flex items-center justify-between gap-4 bg-ink px-4 py-3 text-sheet">
        <h2 id="modelo-130" className="m-0 text-lg leading-snug text-sheet">
          <span className="sr-only">Modelo 130: </span>
          IRPF, pago fraccionado
          <br />
          <span className="text-sm font-normal">{title}, importes acumulados desde enero</span>
        </h2>
        <span aria-hidden="true" className="font-heading text-[28px] font-bold leading-none">
          130
        </span>
      </header>
      {groups.map((entry) => (
        <div key={entry.group} className="border-t border-ink px-4 pb-4 pt-3 first:border-t-0">
          <h3 className="mb-2 text-[13px] text-ink-soft">{entry.label}</h3>
          <ul className="m-0 list-none p-0">
            {entry.boxes.map((box) => (
              <BoxLine key={box.code} view={boxView130(box, model.year)} />
            ))}
          </ul>
        </div>
      ))}
      <footer className="border-t border-ink bg-paper px-4 py-3 text-[15px]">
        <p className="m-0">
          Resultado: <strong>{resultText130(model.result_kind, model.result_cents)}</strong>
        </p>
        {share ? <p className="mb-0 mt-1 text-[13px] text-ink-soft">{share}</p> : null}
      </footer>
    </section>
  );
}
