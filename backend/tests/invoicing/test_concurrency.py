"""AC-19 · Emisiones y rectificativas simultáneas POR LA API (SPEC-W-007 T7-03, Anexo B.1-D).

La numeración sale sin huecos ni repeticiones y una factura se devuelve una sola vez, con peticiones HTTP de verdad desde hilos distintos. Las
carreras directas contra la base están en `tests/rls/test_invoices_concurrency.py`; aquí se comprueba la capa de la API encima.
"""

import threading
from collections import Counter
from collections.abc import Callable
from typing import Any

import httpx2 as httpx

from tests.invoicing.conftest import Api, invoice_body
from tests.rls.invoices_support import D2

THREADS = 20


def run_all(jobs: list[Callable[[], httpx.Response]]) -> list[httpx.Response]:
    """Lanza todas las peticiones a la vez (con una barrera) y devuelve las respuestas."""
    barrier = threading.Barrier(len(jobs))
    results: list[httpx.Response | None] = [None] * len(jobs)

    def work(index: int) -> None:
        barrier.wait()
        results[index] = jobs[index]()

    threads = [threading.Thread(target=work, args=(i,)) for i in range(len(jobs))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)
    assert all(not t.is_alive() for t in threads), "alguna petición no terminó"
    return [r for r in results if r is not None]


def test_twenty_simultaneous_issues_get_twenty_consecutive_numbers(api: Api) -> None:
    body = invoice_body(api.cid())
    responses = run_all([lambda: api.issue(api.cast.alicia, body) for _ in range(THREADS)])
    assert [r.text for r in responses if r.status_code != 201] == []
    numbers = sorted(r.json()["number"] for r in responses)
    assert numbers == list(range(1, THREADS + 1))
    assert len({r.json()["id"] for r in responses}) == THREADS
    row = api.admin.execute(
        "select next_number from public.invoice_series where id = %s", (api.world.series,)
    ).fetchone()
    assert row == {"next_number": THREADS + 1}


def test_five_simultaneous_full_cancellations_give_the_invoice_back_once(api: Api) -> None:
    original = api.made(api.cast.alicia)
    responses = run_all(
        [lambda: api.rectify(api.cast.alicia, original["id"], corrected_base_cents=0) for _ in range(5)]
    )
    assert sum(1 for r in responses if r.status_code == 201) == 1, [r.text for r in responses]
    losers = [r for r in responses if r.status_code != 201]
    assert Counter(r.status_code for r in losers) == {422: 4}
    assert {f["field"] for r in losers for f in r.json()["fields"]} == {"corrected_base_cents"}
    total: Any = api.admin.execute(
        "select sum(base_cents) as b, sum(vat_cents) as v, sum(irpf_cents) as i from public.invoices where id = %s or rectifies_id = %s",
        (original["id"], original["id"]),
    ).fetchone()
    assert total == {"b": 0, "v": 0, "i": 0}


def test_simultaneous_partial_rectifications_never_give_back_more_than_the_invoice(api: Api) -> None:
    original = api.made(api.cast.alicia)
    responses = run_all(
        [
            lambda b=base: api.rectify(
                api.cast.alicia, original["id"], corrected_base_cents=b, issue_date=D2.isoformat()
            )
            for base in (90_000, 80_000, 70_000, 60_000, 50_000)
        ]
    )
    assert sum(1 for r in responses if r.status_code == 201) >= 1
    assert all(r.status_code in {201, 409, 422} for r in responses), [r.text for r in responses]
    standing = api.get(api.cast.alicia, original["id"]).json()["standing"]
    assert 0 <= standing["base_cents"] <= 100_000 and standing["vat_cents"] >= 0 and standing["irpf_cents"] >= 0
    # lo vigente es exactamente la base más lo que sumaron las rectificativas emitidas
    row = api.admin.execute(
        "select sum(base_cents) as b from public.invoices where id = %s or rectifies_id = %s",
        (original["id"], original["id"]),
    ).fetchone()
    assert row == {"b": standing["base_cents"]}
