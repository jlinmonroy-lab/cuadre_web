"""AC-14 a AC-17 · Las políticas de `storage.objects` del bucket `logos` (SPEC-W-005 §5.2, T5-04, T5-06, Anexo B.1).

Se prueban por SQL, con el mismo rol y las mismas claims que usa Storage al atender una petición. `test_logo_storage_live.py` repite lo esencial
contra la API real. `storage.objects` no admite `DELETE` directo (lo prohíbe un trigger de Storage): la regla de borrado se prueba llamando a la
función que usa la política.
"""

import uuid
from collections.abc import Iterator

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Outcome, Person, Pool, apply_scenario, attempt

SCENARIOS = ["baseline", "pending", "active", "revoked", "declined"]
FILE = "0123abcd-4567-89ab-cdef-0123456789ab"


class Objects:
    """Filas de storage.objects creadas por un test; el fixture las retira al terminar."""

    def __init__(self, admin: Connection[DictRow]) -> None:
        self.admin = admin
        self.paths: list[str] = []

    def put(self, path: str) -> None:
        self.admin.execute("insert into storage.objects (bucket_id, name) values ('logos', %s)", (path,))
        self.paths.append(path)


@pytest.fixture
def objects(admin: Connection[DictRow]) -> Iterator[Objects]:
    store = Objects(admin)
    yield store
    if store.paths:
        admin.execute("select set_config('storage.allow_delete_query', 'true', false)")
        admin.execute("delete from storage.objects where bucket_id = 'logos' and name = any(%s)", (store.paths,))
        admin.execute("select set_config('storage.allow_delete_query', 'false', false)")


def path_of(person: Person, name: str = f"{FILE}.png") -> str:
    return f"{person.id}/{name}"


def insert_object(pool: Pool, person: Person, path: str) -> Outcome:
    return attempt(
        pool,
        person,
        "insert into storage.objects (bucket_id, name, owner_id) values ('logos', %s, %s)",
        (path, str(person.id)),
    )


def uploaded(out: Outcome) -> bool:
    return not out.error and out.rowcount == 1


def can_read(pool: Pool, person: Person, path: str) -> bool:
    out = attempt(pool, person, "select name from storage.objects where bucket_id = 'logos' and name = %s", (path,))
    assert not out.error, out.message
    return bool(out.rows)


def helper(pool: Pool, person: Person, function: str, name: str) -> bool:
    out = attempt(pool, person, f"select private.{function}(%s) as ok", (name,))
    assert not out.error, f"{function}({name!r}) lanzó {out.message}"
    return bool(out.rows[0]["ok"])


# --- subir (la política de INSERT se evalúa al firmar) -----------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ["png", "jpg", "webp"])
@pytest.mark.parametrize("who", ["alicia", "beto"])
def test_a_usuario_uploads_to_their_own_folder(
    app_pool: Pool, objects: Objects, cast: Cast, who: str, ext: str
) -> None:
    person = cast[who]
    path = path_of(person, f"{uuid.uuid4()}.{ext}")
    assert uploaded(insert_object(app_pool, person, path))
    objects.paths.append(path)


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_upload_not_even_to_their_own_folder(app_pool: Pool, cast: Cast, who: str) -> None:
    """T5-04: la política exige el rol `usuario` (B.1: sin esa condición podrían firmar a su propia carpeta)."""
    assert not uploaded(insert_object(app_pool, cast[who], path_of(cast[who])))


@pytest.mark.parametrize("who", ["beto", "gina", "gus", "adan"])
def test_nobody_uploads_to_alicias_folder(app_pool: Pool, cast: Cast, who: str) -> None:
    assert not uploaded(insert_object(app_pool, cast[who], path_of(cast.alicia)))


def test_a_suspended_account_uploads_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert not uploaded(insert_object(app_pool, cast.alicia, path_of(cast.alicia)))


@pytest.mark.parametrize(
    "name",
    [
        f"{FILE}.svg",
        f"{FILE}.gif",
        f"{FILE}.pdf",
        f"{FILE}.PNG",
        f"{FILE}.png.png",
        f"{FILE}",
        "logo.png",
        f"x/{FILE}.png",
        f"{FILE.upper()}.png",
        "not-a-uuid.png",
        f"{FILE}.png/",
        ".png",
        "",
    ],
)
def test_the_name_must_be_a_lowercase_uuid_with_one_of_the_three_extensions(
    app_pool: Pool, cast: Cast, name: str
) -> None:
    assert not uploaded(insert_object(app_pool, cast.alicia, path_of(cast.alicia, name)))


def test_the_folder_must_be_exactly_one_level(app_pool: Pool, cast: Cast) -> None:
    for path in (f"{FILE}.png", f"{cast.alicia.id}", f"{cast.alicia.id}//{FILE}.png", f"a/{cast.alicia.id}/{FILE}.png"):
        assert not uploaded(insert_object(app_pool, cast.alicia, path)), path


def test_files_are_never_overwritten(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    path = path_of(cast.alicia)
    objects.put(path)
    out = attempt(
        app_pool,
        cast.alicia,
        "update storage.objects set metadata = '{}'::jsonb where bucket_id = 'logos' and name = %s",
        (path,),
    )
    assert not out.error and out.rowcount == 0, "no hay política de UPDATE"


# --- leer ---------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_who_can_read_alicias_logo_in_each_link_state(
    app_pool: Pool, cast: Cast, objects: Objects, scenario: str
) -> None:
    apply_scenario(app_pool, cast, scenario)
    alicia_logo, beto_logo = path_of(cast.alicia), path_of(cast.beto)
    objects.put(alicia_logo)
    objects.put(beto_logo)

    expected = {"alicia": True, "beto": False, "gina": scenario == "active", "gus": False, "adan": False}
    for key, allowed in expected.items():
        assert can_read(app_pool, cast[key], alicia_logo) is allowed, f"{scenario}: {key} y el logo de alicia"
    assert can_read(app_pool, cast.beto, beto_logo)
    assert not can_read(app_pool, cast.alicia, beto_logo)
    assert not can_read(app_pool, cast.gina, beto_logo), "el gestor solo lee a quien le dio acceso"


def test_the_admin_reads_no_logo_not_even_their_own_row_of_another(
    app_pool: Pool, cast: Cast, objects: Objects
) -> None:
    objects.put(path_of(cast.alicia))
    out = attempt(app_pool, cast.adan, "select count(*) as n from storage.objects where bucket_id = 'logos'")
    assert not out.error and out.rows[0]["n"] == 0


def test_a_stranger_cannot_list_another_persons_folder(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    objects.put(path_of(cast.alicia))
    out = attempt(
        app_pool,
        cast.beto,
        "select name from storage.objects where bucket_id = 'logos' and name like %s",
        (f"{cast.alicia.id}/%",),
    )
    assert not out.error and out.rows == []


# --- borrar ------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("who", "allowed"), [("alicia", True), ("beto", False), ("gina", False), ("gus", False), ("adan", False)]
)
def test_only_the_owner_deletes(app_pool: Pool, cast: Cast, who: str, allowed: bool) -> None:
    assert helper(app_pool, cast[who], "logo_can_delete", path_of(cast.alicia)) is allowed


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_delete_from_their_own_folder_either(app_pool: Pool, cast: Cast, who: str) -> None:
    """La política de borrado exige el rol `usuario` igual que la de subida (T5-04)."""
    assert helper(app_pool, cast[who], "logo_can_delete", path_of(cast[who])) is False
    assert helper(app_pool, cast[who], "logo_can_upload", path_of(cast[who])) is False


def test_a_gestor_with_an_active_link_cannot_delete_either(app_pool: Pool, cast: Cast) -> None:
    apply_scenario(app_pool, cast, "active")
    assert helper(app_pool, cast.gina, "logo_can_delete", path_of(cast.alicia)) is False
    assert helper(app_pool, cast.gina, "logo_can_read", path_of(cast.alicia)) is True
    assert helper(app_pool, cast.gina, "logo_can_upload", path_of(cast.alicia)) is False


# --- rutas raras: denegación, nunca un error -----------------------------------------------------------------------------------------------

WEIRD = [
    "",
    "x",
    "/",
    "//",
    "not-a-uuid/x.png",
    "%s/not-a-uuid.png",
    "%s/" + FILE + ".png/extra",
    "%s//" + FILE + ".png",
    "%s",
    "%s/",
    "%s/a/b.png",
    "../%s/" + FILE + ".png",
    "%s/" + FILE + ".png\n",
    "\n%s/" + FILE + ".png",
    "ffffffff-ffff-ffff-ffff-fffffffffffg/" + FILE + ".png",
]


@pytest.mark.parametrize("function", ["logo_can_upload", "logo_can_read", "logo_can_delete"])
def test_malformed_paths_are_denied_not_errors(app_pool: Pool, cast: Cast, function: str) -> None:
    """B.1: una política en línea con `::uuid` fallaba con un error ante `not-a-uuid/x.png`; con estas funciones, denegación."""
    names = [n.replace("%s", str(cast.alicia.id)) for n in WEIRD] + [f"{str(cast.alicia.id).upper()}/{FILE}.png"]
    for name in names:
        assert helper(app_pool, cast.alicia, function, name) is False, f"{function}({name!r})"


def test_the_folder_owner_function_reads_only_the_exact_shape(admin: Connection[DictRow], cast: Cast) -> None:
    """`logo_folder_owner` es un ayudante interno: no se concede a nadie, se consulta como dueño de la base."""

    def owner(name: str) -> object:
        row = admin.execute("select private.logo_folder_owner(%s) as o", (name,)).fetchone()
        assert row is not None
        return row["o"]

    assert owner(path_of(cast.alicia)) == cast.alicia.id
    assert owner(path_of(cast.alicia, f"{FILE}.webp")) == cast.alicia.id
    assert owner(path_of(cast.alicia, f"{FILE}.svg")) is None
    assert owner("x/y/z") is None
    assert owner("") is None
    assert admin.execute(
        "select has_function_privilege('authenticated', 'private.logo_folder_owner(text)', 'EXECUTE') as ok"
    ).fetchone() == {"ok": False}


def test_the_helpers_are_not_reachable_by_anon(app_pool: Pool) -> None:
    import psycopg

    for function in ("logo_can_upload", "logo_can_read", "logo_can_delete"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege), app_pool.connection() as conn:
            conn.execute("SET LOCAL ROLE anon")
            conn.execute(f"select private.{function}('x/y')")


def test_the_three_policies_exist_and_are_for_authenticated_only(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select policyname, cmd, roles from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname like 'logos_%'"
    ).fetchall()
    assert {(r["policyname"], r["cmd"]) for r in rows} == {
        ("logos_objects_insert", "INSERT"),
        ("logos_objects_select", "SELECT"),
        ("logos_objects_delete", "DELETE"),
    }
    assert all(list(r["roles"]) == ["authenticated"] for r in rows)
