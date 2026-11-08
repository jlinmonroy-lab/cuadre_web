"""AC-14 a AC-16 · `app.set_business_logo` y `app.clear_business_logo` (SPEC-W-005 §5.2, D-13).

`logo_path` no se puede escribir directamente (lo prueba `test_profile_constraints.py`): estas dos funciones son la única vía, y comprueban que la
ruta sea `{auth.uid()}/{uuid}.{png|jpg|webp}`. Devuelven la ruta ANTERIOR para que la API borre ese objeto de Storage. Los roles están en
`test_invoice_series.py`.
"""

import uuid

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Outcome, Person, Pool, call


def new_path(person: Person, ext: str = "png") -> str:
    return f"{person.id}/{uuid.uuid4()}.{ext}"


def logo_of(admin: Connection[DictRow], person: Person) -> str | None:
    row = admin.execute("select logo_path from public.business_profiles where owner_id = %s", (person.id,)).fetchone()
    assert row is not None
    return row["logo_path"]


def returned(out: Outcome) -> object:
    assert not out.error, out.message
    return next(iter(out.rows[0].values()))


def code_of(out: Outcome) -> str:
    assert out.sqlstate == "P0001", (out.sqlstate, out.message)
    return (out.message or "").strip()


def test_setting_a_logo_stores_the_path_and_returns_nothing_the_first_time(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    path = new_path(cast.alicia)
    assert returned(call(app_pool, cast.alicia, "set_business_logo", path)) is None
    assert logo_of(admin, cast.alicia) == path


@pytest.mark.parametrize("ext", ["png", "jpg", "webp"])
def test_the_three_extensions(app_pool: Pool, admin: Connection[DictRow], cast: Cast, ext: str) -> None:
    path = new_path(cast.alicia, ext)
    assert not call(app_pool, cast.alicia, "set_business_logo", path).error
    assert logo_of(admin, cast.alicia) == path


def test_replacing_the_logo_returns_the_previous_path(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    first, second = new_path(cast.alicia), new_path(cast.alicia, "jpg")
    call(app_pool, cast.alicia, "set_business_logo", first)
    assert returned(call(app_pool, cast.alicia, "set_business_logo", second)) == first
    assert logo_of(admin, cast.alicia) == second


def test_clearing_returns_the_path_and_empties_it(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    path = new_path(cast.alicia)
    call(app_pool, cast.alicia, "set_business_logo", path)
    assert returned(call(app_pool, cast.alicia, "clear_business_logo")) == path
    assert logo_of(admin, cast.alicia) is None


def test_clearing_without_a_logo_is_not_an_error(app_pool: Pool, cast: Cast) -> None:
    assert returned(call(app_pool, cast.alicia, "clear_business_logo")) is None
    assert returned(call(app_pool, cast.alicia, "clear_business_logo")) is None


def test_the_other_profile_columns_are_not_touched(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute(
        "update public.business_profiles set legal_name = 'Alicia Demo', iban = 'ES3600000000050000000001' where owner_id = %s",
        (cast.alicia.id,),
    )
    call(app_pool, cast.alicia, "set_business_logo", new_path(cast.alicia))
    call(app_pool, cast.alicia, "clear_business_logo")
    row = admin.execute(
        "select legal_name, iban from public.business_profiles where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert row == {"legal_name": "Alicia Demo", "iban": "ES3600000000050000000001"}


def test_each_person_has_their_own_logo(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    mine, yours = new_path(cast.alicia), new_path(cast.beto)
    call(app_pool, cast.alicia, "set_business_logo", mine)
    call(app_pool, cast.beto, "set_business_logo", yours)
    call(app_pool, cast.alicia, "clear_business_logo")
    assert logo_of(admin, cast.alicia) is None and logo_of(admin, cast.beto) == yours


FILE = "0123abcd-4567-89ab-cdef-0123456789ab"


@pytest.mark.parametrize(
    "name",
    [
        f"{FILE}.svg",
        f"{FILE}.gif",
        f"{FILE}.PNG",
        "logo.png",
        f"x/{FILE}.png",
        f"{FILE.upper()}.png",
        f"{FILE}.png\n",
        "not-a-uuid.png",
        f"{FILE}",
        "",
    ],
)
def test_a_path_that_is_not_the_exact_shape_is_refused(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, name: str
) -> None:
    out = call(app_pool, cast.alicia, "set_business_logo", f"{cast.alicia.id}/{name}")
    assert code_of(out) == "invalid_logo"
    assert logo_of(admin, cast.alicia) is None


def test_another_persons_folder_is_refused(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    assert code_of(call(app_pool, cast.alicia, "set_business_logo", new_path(cast.beto))) == "invalid_logo"
    assert code_of(call(app_pool, cast.alicia, "set_business_logo", f"{uuid.uuid4()}/{FILE}.png")) == "invalid_logo"
    assert logo_of(admin, cast.alicia) is None and logo_of(admin, cast.beto) is None


@pytest.mark.parametrize("path", [None, "", "x"])
def test_an_empty_or_odd_path_is_refused(app_pool: Pool, cast: Cast, path: str | None) -> None:
    assert code_of(call(app_pool, cast.alicia, "set_business_logo", path)) == "invalid_logo"


def test_the_logo_functions_write_nothing_to_the_activity_log(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    def count() -> int:
        row = admin.execute(
            "select count(*) as n from public.activity_log where owner_id = %s", (cast.alicia.id,)
        ).fetchone()
        assert row is not None
        return int(row["n"])

    before = count()  # el alta de la cuenta ya escribe la suya
    call(app_pool, cast.alicia, "set_business_logo", new_path(cast.alicia))
    call(app_pool, cast.alicia, "clear_business_logo")
    assert count() == before
