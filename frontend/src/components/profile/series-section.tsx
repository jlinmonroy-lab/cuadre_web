import { AddSeries, SeriesActions, type SeriesRow } from "@/components/profile/series-actions";

const TAG = "rounded-full px-2.5 py-0.5 text-[13px] font-semibold";

/** «Predeterminada», «Archivada» y «En uso»: siempre texto; el color solo refuerza. */
function Tags({ series }: { series: SeriesRow }) {
  if (!series.is_default && !series.archived && !series.in_use) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Marcas de la serie">
      {series.is_default ? <li className={`${TAG} bg-action-soft text-action-hover`}>Predeterminada</li> : null}
      {series.archived ? <li className={`${TAG} bg-muted text-ink-soft`}>Archivada</li> : null}
      {series.in_use ? <li className={`${TAG} bg-scope-eu-bg text-scope-eu`}>En uso</li> : null}
    </ul>
  );
}

/**
 * Series de facturación: tarjetas apiladas hasta 1.279 px y tabla desde 1.280 (como Gastos, T3-11). Las dos vistas están en el DOM y solo
 * una se muestra (la otra va con `display: none`, así que no existe para el lector de pantalla). Cada serie lleva el número que
 * corresponde a la siguiente factura; emitir y numerar es de SPEC-W-007.
 */
export function SeriesSection({ series }: { series: SeriesRow[] }) {
  return (
    <div className="grid gap-4">
      {series.length === 0 ? (
        <p className="rounded-panel border border-rule bg-sheet px-5 py-6 text-center text-ink-soft">
          Todavía no tienes series. La serie del año se crea sola al guardar tu perfil.
        </p>
      ) : (
        <>
          <ul className="grid gap-3 min-[1280px]:hidden">
            {series.map((item) => (
              <li key={item.id}>
                <article className="grid gap-3 rounded-panel border border-rule bg-sheet p-4">
                  <div className="grid gap-1.5">
                    <h3 className="text-[15px] leading-snug">Serie {item.code}</h3>
                    {item.description ? <p className="text-[13px] text-ink-soft [overflow-wrap:anywhere]">{item.description}</p> : null}
                    <p className="text-[13px] text-ink-soft">
                      Siguiente número: <span className="font-semibold tabular-nums text-ink">{item.next_number}</span>
                    </p>
                    <Tags series={item} />
                  </div>
                  <SeriesActions series={item} view="tarjeta" />
                </article>
              </li>
            ))}
          </ul>

          <div className="hidden min-[1280px]:block">
            <table className="w-full border-collapse text-left text-[15px]">
              <caption className="sr-only">Series de facturación, la predeterminada primero</caption>
              <thead>
                <tr className="border-b border-rule-strong text-[13px] text-ink-soft">
                  <th scope="col" className="w-28 py-2 pr-4 font-semibold">
                    Código
                  </th>
                  <th scope="col" className="py-2 pr-4 font-semibold">
                    Descripción
                  </th>
                  <th scope="col" className="w-36 py-2 pr-4 text-right font-semibold">
                    Siguiente número
                  </th>
                  <th scope="col" className="w-56 py-2 pr-4 font-semibold">
                    Marcas
                  </th>
                  <th scope="col" className="w-96 py-2 font-semibold">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody>
                {series.map((item) => (
                  <tr key={item.id} className="border-b border-rule align-top hover:bg-sheet">
                    <th scope="row" className="py-3 pr-4 font-bold">
                      {item.code}
                    </th>
                    <td className="py-3 pr-4 [overflow-wrap:anywhere]">{item.description ?? <span className="text-ink-soft">Sin descripción</span>}</td>
                    <td className="py-3 pr-4 text-right font-semibold tabular-nums">{item.next_number}</td>
                    <td className="py-3 pr-4">
                      <Tags series={item} />
                    </td>
                    <td className="py-3">
                      <SeriesActions series={item} view="tabla" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <AddSeries />
    </div>
  );
}
