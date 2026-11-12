import { BoxRow } from "@/components/tax/box-row";
import { OWNER_LINKS, groupBoxes, quarterTitle, resultText, type Modelo303, type Quarter, type TaxLinks } from "@/lib/tax";

/**
 * La hoja del modelo 303 como el prototipo: cabecera oscura, las casillas agrupadas y el resultado al pie. Todo lo que enseña lo calculó el
 * servidor; aquí solo se ordena y se escribe. Es un borrador orientativo: no hay botón de presentar.
 */
export function Modelo303Sheet({ model, links = OWNER_LINKS }: { model: Modelo303; links?: TaxLinks }) {
  const groups = groupBoxes(model.boxes);
  const title = quarterTitle(model.year, model.quarter as Quarter);
  return (
    <section aria-labelledby="modelo-303" className="max-w-3xl border border-ink bg-sheet">
      <header className="flex items-center justify-between gap-4 bg-ink px-4 py-3 text-sheet">
        <h2 id="modelo-303" className="m-0 text-lg leading-snug text-sheet">
          <span className="sr-only">Modelo 303: </span>
          IVA, autoliquidación
          <br />
          <span className="text-sm font-normal">{title}</span>
        </h2>
        <span aria-hidden="true" className="font-heading text-[28px] font-bold leading-none">
          303
        </span>
      </header>
      {groups.map((entry) => (
        <div key={entry.group} className="border-t border-ink px-4 pb-4 pt-3 first:border-t-0">
          <h3 className="mb-2 text-[13px] text-ink-soft">{entry.label}</h3>
          <ul className="m-0 list-none p-0">
            {entry.boxes.map((box) => (
              <BoxRow key={box.code} box={box} links={links} />
            ))}
          </ul>
        </div>
      ))}
      <footer className="border-t border-ink bg-paper px-4 py-3 text-[15px]">
        Resultado: <strong>{resultText(model.result_kind, model.result_cents)}</strong>
      </footer>
    </section>
  );
}
