"""Los cinco trimestres de la spec (SPEC-W-008, Anexo B.1) sembrados en la base de datos real con las funciones `app.*` y la inserción directa de gastos.

Se siembra una sola vez por módulo, con un reparto de personas propio (`make_cast`): las facturas no se pueden borrar, así que no hay forma de
limpiar, y repetir la siembra en cada prueba solo alargaría la suite. Todo es sintético y reconocible. Las facturas se emiten por la función de la
base (la misma que la API), así que los importes de las rectificativas los calcula `cuadre.tax` y los guarda la base: si no coincidieran con lo
calculado a mano en B.1, estas pruebas lo dirían.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.tax import Standing
from tests.rls.expenses_support import insert, manual, params
from tests.rls.invoices_support import issue, made, ready, rectify, series
from tests.support import Cast, Pool, make_cast, new_document
from tests.tax.test_modelo_303_cases import CASES

# Qué factura rectifica cada rectificativa y la base que queda (Anexo B.1, columna «Cuenta de la cuota»).
RECTIFICATIONS = {
    "R1": ("B1", 60_000),
    "R2": ("B2", 100_000),
    "R3": ("C1", 0),
    "R4": ("C2", 1_105),
    "R5": ("C3", 53),
    "R6": ("C3", 0),
}
# Tratamiento fiscal -> (ámbito y tipo de cliente) que lo produce.
CLIENT_OF = {
    "national_vat": ("national", "business"),
    "eu_reverse_charge": ("eu", "business"),
    "non_eu_not_subject": ("non_eu", "business"),
    "eu_consumer_vat": ("eu", "individual"),
    "non_eu_consumer_vat": ("non_eu", "individual"),
}


@dataclass
class Seeded:
    cast: Cast
    to_db: dict[str, str]  # id de B.1 -> id en la base

    @property
    def from_db(self) -> dict[str, str]:
        return {v: k for k, v in self.to_db.items()}


def standing_of(admin: Connection[DictRow], invoice_id: object) -> Standing:
    """Lo vigente de una factura: ella más sus rectificativas, leído de la base."""
    row = admin.execute(
        "select i.base_cents + coalesce(sum(r.base_cents), 0) as base, i.vat_cents + coalesce(sum(r.vat_cents), 0) as vat, "
        "i.irpf_cents + coalesce(sum(r.irpf_cents), 0) as irpf from public.invoices i "
        "left join public.invoices r on r.rectifies_id = i.id where i.id = %s group by i.id",
        (invoice_id,),
    ).fetchone()
    assert row is not None
    return Standing(int(row["base"]), int(row["vat"]), int(row["irpf"]))


def _expense(admin: Connection[DictRow], pool: Pool, cast: Cast, document: dict[str, Any]) -> str:
    day = date.fromisoformat(document["fecha"])
    if not document["lineas"]:  # el manual sin IVA
        return str(insert(admin, manual(cast.alicia, date=day, name=document["id"], base=5_000, total=5_000)))
    lines = [{"vat_rate": str(x["iva"]), "base_cents": x["base"], "vat_cents": x["cuota"]} for x in document["lineas"]]
    base, vat = sum(x["base_cents"] for x in lines), sum(x["vat_cents"] for x in lines)
    values = params(
        cast.alicia,
        new_document(pool, cast.alicia),
        date=day,
        name=document["id"],
        number=f"N-{document['id']}",
        base=base,
        vat=vat,
        total=base + vat,
        lines=lines,
        deductible=document["iva_deducible"],
        voided=datetime.now(UTC) if document["anulado"] else None,
    )
    return str(insert(admin, values))


def seed(admin: Connection[DictRow], pool: Pool) -> Seeded:
    cast = make_cast(admin)
    r = ready(admin, cast.alicia)  # la serie 2026 y un cliente de cada ámbito y tipo
    by_year = {2026: r.series, 2025: series(admin, cast.alicia, "2025")}
    documents = [d for t in CASES["trimestres"] for d in t["documentos"]] + CASES["fuera_de_los_cinco"]
    by_id = {d["id"]: d for d in documents}
    to_db: dict[str, str] = {}

    # Primero las ordinarias en orden cronológico (la numeración de cada serie no admite fechas hacia atrás).
    for d in sorted((d for d in documents if d["tipo"] == "factura"), key=lambda d: (d["fecha"], d["id"])):
        scope, kind = CLIENT_OF[d["tratamiento"]]
        has_vat = d["tratamiento"] in ("national_vat", "eu_consumer_vat", "non_eu_consumer_vat")
        out = issue(
            pool,
            cast.alicia,
            r.clients[(scope, kind)],
            by_year[int(d["fecha"][:4])],
            when=date.fromisoformat(d["fecha"]),
            base=d["base"],
            scope=scope,
            kind=kind,
            vat=str(d["iva"]) if has_vat else None,
        )
        to_db[d["id"]] = str(made(out))

    # Después las rectificativas, en orden cronológico, con lo vigente de la base en ese momento.
    for d in sorted((d for d in documents if d["tipo"] == "rectificativa"), key=lambda d: (d["fecha"], d["id"])):
        original_id, corrected = RECTIFICATIONS[d["id"]]
        original = by_id[original_id]
        withholds = original["tratamiento"] == "national_vat"
        out = rectify(
            pool,
            cast.alicia,
            to_db[original_id],
            corrected=corrected,
            when=date.fromisoformat(d["fecha"]),
            standing=standing_of(admin, to_db[original_id]),
            vat=str(original["iva"]),
            irpf="15" if withholds else "0",
        )
        to_db[d["id"]] = str(made(out))

    for d in sorted((d for d in documents if d["tipo"] == "gasto"), key=lambda d: (d["fecha"], d["id"])):
        to_db[d["id"]] = _expense(admin, pool, cast, d)
    return Seeded(cast, to_db)


@pytest.fixture(scope="module")
def seeded(admin: Connection[DictRow], app_pool: Pool) -> Iterator[Seeded]:
    yield seed(admin, app_pool)
