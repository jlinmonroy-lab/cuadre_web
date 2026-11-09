"""AC-13 · Dos peticiones a la vez con el mismo NIF: una gana y la otra recibe nuestro 409, nunca un 500 (cerrojo por persona, B.1-C y B.3)."""

import threading
from typing import Any

from tests.clients.conftest import BODY, Api


def together(*jobs: Any) -> list[int]:
    """Lanza los trabajos a la vez (con una barrera) y devuelve los códigos HTTP, ordenados."""
    codes: list[int] = []
    barrier = threading.Barrier(len(jobs))

    def run(job: Any) -> None:
        barrier.wait()
        codes.append(job().status_code)

    threads = [threading.Thread(target=run, args=(job,)) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads), "una petición no terminó"
    return sorted(codes)


def test_ac13_two_creations_with_the_same_tax_id_give_201_and_409(api: Api) -> None:
    codes = together(lambda: api.create(api.cast.alicia), lambda: api.create(api.cast.alicia, name="Otro S.L."))
    assert codes == [201, 409]
    assert len(api.listing(api.cast.alicia, archived=True)) == 1


def test_many_creations_at_once_leave_exactly_one(api: Api) -> None:
    codes = together(*[lambda i=i: api.create(api.cast.alicia, name=f"Cliente {i} S.L.") for i in range(5)])
    assert codes == [201, 409, 409, 409, 409]
    assert len(api.listing(api.cast.alicia)) == 1


def test_a_creation_and_a_reactivation_with_the_same_tax_id_at_the_same_time(api: Api) -> None:
    old = api.made(api.cast.alicia)
    api.archive(api.cast.alicia, old["id"], True)
    codes = together(
        lambda: api.create(api.cast.alicia, name="Nuevo S.L."), lambda: api.archive(api.cast.alicia, old["id"], False)
    )
    assert codes in ([200, 409], [201, 409])  # gana quien toma el cerrojo primero; el otro ve su resultado y choca
    active = [
        c for c in api.listing(api.cast.alicia, archived=True) if not c["archived"] and c["tax_id"] == BODY["tax_id"]
    ]
    assert len(active) == 1


def test_two_people_creating_the_same_tax_id_do_not_interfere(api: Api) -> None:
    assert together(lambda: api.create(api.cast.alicia), lambda: api.create(api.cast.beto)) == [201, 201]
