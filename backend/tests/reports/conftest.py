"""Ayudas de las pruebas de API del reporte mensual (SPEC-W-013 §5.3): la aplicación REAL con base de datos real y un reloj fijo, y los documentos de la historia.

Agosto y septiembre de 2026 quedan cerrados por el job de verdad; octubre (terminado, sin cierre) y noviembre (en curso) se calculan en vivo.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import Connection
from psycopg.rows import DictRow

from cuadre.core.auth import JwksTokenVerifier
from cuadre.jobs.closing_job import run_monthly_closing
from cuadre.main import create_app
from tests.agents.support import make_settings
from tests.api.conftest import FakeJwksClient, Signer, jwks_client, signer  # noqa: F401 - fixtures de otro conftest
from tests.clocks import FixedClock
from tests.jobs.test_cierre_mensual_job import bill, spend
from tests.rls.invoices_support import Ready, ready
from tests.support import Person, Pool

TODAY = datetime(2026, 11, 13, 8, 0, tzinfo=UTC)
OCT_1 = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


@dataclass
class Api:
    app: FastAPI
    client: TestClient
    signer: Signer

    def get(self, person: Person | None, path: str) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.signer.token(person)}"} if person is not None else {}
        return self.client.get(path, headers=headers)

    def report(self, person: Person | None, year: int, month: int) -> httpx.Response:
        return self.get(person, f"/api/monthly-report/{year}/{month}")

    def month(self, person: Person | None, year: int, month: int) -> httpx.Response:
        return self.get(person, f"/api/monthly-closings/{year}/{month}")


@pytest.fixture
def api(jwks_client: FakeJwksClient, signer: Signer) -> Iterator[Api]:  # noqa: F811
    application = create_app(
        make_settings(database_url=os.environ["DATABASE_URL"], supabase_url=os.environ["SUPABASE_URL"])
    )
    application.state.token_verifier = JwksTokenVerifier(os.environ["SUPABASE_URL"], jwk_client=jwks_client)
    application.state.clock = FixedClock(TODAY)
    with TestClient(application, raise_server_exceptions=False) as client:
        yield Api(application, client, signer)


def close_until(service_pool: Pool, app_pool: Pool, person: Person, now: datetime = OCT_1) -> None:
    """Corre el job como el planificador: cierra los meses terminados hasta `now`."""
    run_monthly_closing(service_pool=service_pool, app_pool=app_pool, now=now, only_owners=[person.id])


def expense(
    admin: Connection[DictRow],
    app_pool: Pool,
    person: Person,
    when: date,
    category: str,
    base: int,
    vat: int = 0,
    *,
    deductible: bool = False,
    voided: datetime | None = None,
) -> Any:
    """Un gasto de documento con su categoría, su IVA (deducible o no) y, si se pide, ya anulado. Las líneas suman la base y el IVA."""
    line = {"vat_rate": "21" if vat else "0", "base_cents": base, "vat_cents": vat}
    return spend(
        admin,
        app_pool,
        person,
        when,
        category=category,
        base=base,
        vat=vat,
        total=base + vat,
        lines=[line],
        deductible=deductible and vat > 0,
        voided=voided,
    )


def story(admin: Connection[DictRow], app_pool: Pool, service_pool: Pool, person: Person) -> Ready:
    """Agosto y septiembre cerrados, octubre (terminado) sin cerrar y noviembre en curso.

    Agosto: 1.000,00 € nacional; software 100,00 €.
    Septiembre: 900,00 € nacional y 300,00 € de la UE (total 1.200,00 €, un 20 % más); software 60,50 € (IVA no deducible incluido), asesoría 300,00 € y un
    gasto anulado de material que no debe contar.
    Octubre: 200,00 € nacional. Noviembre: 70,00 € de fuera de la UE y un gasto de 40,00 €.
    """
    r = ready(admin, person)
    bill(app_pool, admin, person, r, "national", date(2026, 8, 5), 100_000)
    expense(admin, app_pool, person, date(2026, 8, 10), "software", 10_000, 2_100, deductible=True)
    bill(app_pool, admin, person, r, "national", date(2026, 9, 3), 90_000)
    bill(app_pool, admin, person, r, "eu", date(2026, 9, 10), 30_000)
    expense(admin, app_pool, person, date(2026, 9, 5), "software", 5_000, 1_050)
    expense(admin, app_pool, person, date(2026, 9, 6), "advisory", 30_000)
    expense(admin, app_pool, person, date(2026, 9, 7), "supplies", 99_999, voided=datetime(2026, 9, 8, tzinfo=UTC))
    close_until(service_pool, app_pool, person)
    bill(app_pool, admin, person, r, "national", date(2026, 10, 5), 20_000)
    bill(app_pool, admin, person, r, "non_eu", date(2026, 11, 4), 7_000)
    expense(admin, app_pool, person, date(2026, 11, 3), "other", 4_000)
    return r
