"""AC-22 y AC-23 · Las políticas de `storage.objects` del bucket privado `invoices` (SPEC-W-007 §5.2, D-03, Anexo B.1-C).

Se prueban por SQL, con el mismo rol y las mismas claims que usa Storage al atender una petición; `test_invoices_storage_live.py` repite lo
esencial contra la API real. `storage.objects` no admite `DELETE` directo (lo prohíbe un trigger de Storage): se limpia con el permiso que el propio
Storage prevé para ello. Solo hay política de insertar y de leer: sin `UPDATE` ni `DELETE`, un PDF subido no se sustituye.
"""

import uuid
from collections.abc import Iterator

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Outcome, Person, Pool, apply_scenario, attempt

SCENARIOS = ["baseline", "pending", "active", "revoked", "declined"]
SHA16 = "0123456789abcdef"


def file_name(invoice_id: object | None = None, sha: str = SHA16) -> str:
    return f"{invoice_id or uuid.uuid4()}-{sha}.pdf"


class Objects:
    """Filas de storage.objects creadas por un test; el fixture las retira al terminar."""

    def __init__(self, admin: Connection[DictRow]) -> None:
        self.admin = admin
        self.paths: list[str] = []

    def put(self, path: str) -> None:
        self.admin.execute("insert into storage.objects (bucket_id, name) values ('invoices', %s)", (path,))
        self.paths.append(path)


@pytest.fixture
def objects(admin: Connection[DictRow]) -> Iterator[Objects]:
    store = Objects(admin)
    yield store
    if store.paths:
        admin.execute("select set_config('storage.allow_delete_query', 'true', false)")
        admin.execute("delete from storage.objects where bucket_id = 'invoices' and name = any(%s)", (store.paths,))
        admin.execute("select set_config('storage.allow_delete_query', 'false', false)")


def path_of(person: Person, name: str | None = None) -> str:
    return f"{person.id}/{file_name() if name is None else name}"


def insert_object(pool: Pool, person: Person, path: str, bucket: str = "invoices") -> Outcome:
    return attempt(
        pool,
        person,
        "insert into storage.objects (bucket_id, name, owner_id) values (%s, %s, %s)",
        (bucket, path, str(person.id)),
    )


def uploaded(out: Outcome) -> bool:
    return not out.error and out.rowcount == 1


def can_read(pool: Pool, person: Person, path: str) -> bool:
    out = attempt(pool, person, "select name from storage.objects where bucket_id = 'invoices' and name = %s", (path,))
    assert not out.error, out.message
    return bool(out.rows)


def helper(pool: Pool, person: Person, function: str, name: str) -> bool:
    out = attempt(pool, person, f"select private.{function}(%s) as ok", (name,))
    assert not out.error, f"{function}({name!r}) lanzó {out.message}"
    return bool(out.rows[0]["ok"])


# --- El bucket ------------------------------------------------------------------------------------------------------------------------------


def test_the_bucket_is_private_one_mebibyte_and_pdf_only(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select public, file_size_limit, allowed_mime_types from storage.buckets where id = 'invoices'"
    ).fetchone()
    assert row == {"public": False, "file_size_limit": 1_048_576, "allowed_mime_types": ["application/pdf"]}


def test_the_policies_are_exactly_an_insert_and_a_select_for_authenticated(admin: Connection[DictRow]) -> None:
    rows = admin.execute(
        "select policyname, cmd, roles::text as roles from pg_policies where schemaname = 'storage' and tablename = 'objects' "
        "and policyname like 'invoices_objects_%%' order by 1"
    ).fetchall()
    assert rows == [
        {"policyname": "invoices_objects_insert", "cmd": "INSERT", "roles": "{authenticated}"},
        {"policyname": "invoices_objects_select", "cmd": "SELECT", "roles": "{authenticated}"},
    ]


# --- Subir (la política de INSERT se evalúa al firmar) -------------------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["alicia", "beto"])
def test_a_usuario_uploads_to_their_own_folder(app_pool: Pool, objects: Objects, cast: Cast, who: str) -> None:
    path = path_of(cast[who])
    assert uploaded(insert_object(app_pool, cast[who], path))
    objects.paths.append(path)


@pytest.mark.parametrize("who", ["gina", "gus", "adan"])
def test_a_gestor_or_an_admin_cannot_upload_not_even_to_their_own_folder(app_pool: Pool, cast: Cast, who: str) -> None:
    assert not uploaded(insert_object(app_pool, cast[who], path_of(cast[who])))
    assert helper(app_pool, cast[who], "invoice_file_can_upload", path_of(cast[who])) is False


@pytest.mark.parametrize("who", ["beto", "gina", "gus", "adan"])
def test_nobody_uploads_to_alicias_folder(app_pool: Pool, cast: Cast, who: str) -> None:
    assert not uploaded(insert_object(app_pool, cast[who], path_of(cast.alicia)))


def test_a_suspended_account_uploads_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert not uploaded(insert_object(app_pool, cast.alicia, path_of(cast.alicia)))


def test_the_policy_is_only_for_the_invoices_bucket(app_pool: Pool, cast: Cast) -> None:
    """Un PDF con nombre de factura no entra en otro bucket por esta política (cada bucket tiene las suyas)."""
    assert not uploaded(insert_object(app_pool, cast.alicia, path_of(cast.alicia), bucket="documents"))


@pytest.mark.parametrize(
    "name",
    [
        file_name().replace(".pdf", ".png"),
        file_name().replace(".pdf", ".PDF"),
        file_name().replace(".pdf", ".pdf.pdf"),
        file_name().upper(),
        file_name(sha=SHA16[:15]),
        file_name(sha=SHA16.upper()),
        file_name(sha="0123456789abcdeF"),
        file_name(sha=SHA16 + "0"),
        file_name(sha="G" * 16),
        file_name(sha="g" * 16),
        f"{uuid.uuid4()}.pdf",
        f"{uuid.uuid4()}-{SHA16}",
        f"not-a-uuid-{SHA16}.pdf",
        f"x/{file_name()}",
        file_name() + "/",
        f"-{SHA16}.pdf",
        ".pdf",
        "",
    ],
)
def test_the_name_must_be_an_invoice_uuid_a_16_hex_hash_and_pdf(app_pool: Pool, cast: Cast, name: str) -> None:
    assert not uploaded(insert_object(app_pool, cast.alicia, path_of(cast.alicia, name)))


def test_the_folder_must_be_exactly_one_level(app_pool: Pool, cast: Cast) -> None:
    name = file_name()
    for path in (
        name,
        f"{cast.alicia.id}",
        f"{cast.alicia.id}//{name}",
        f"a/{cast.alicia.id}/{name}",
        f"{str(cast.alicia.id).upper()}/{name}",
    ):
        assert not uploaded(insert_object(app_pool, cast.alicia, path)), path


def test_the_helpers_never_raise_on_strange_names(app_pool: Pool, cast: Cast) -> None:
    for name in ("", "/", "//", "no-es-uuid/x.pdf", "ñ/ñ.pdf", "a" * 5000, f"{cast.alicia.id}/" + "z" * 300):
        for function in ("invoice_file_can_upload", "invoice_file_can_read"):
            try:
                helper(app_pool, cast.alicia, function, name)
            except AssertionError as exc:
                raise AssertionError(f"{function} lanzó con {name[:40]!r}") from exc


# --- Nadie sustituye ni borra -------------------------------------------------------------------------------------------------------------


def test_files_are_never_overwritten(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    path = path_of(cast.alicia)
    objects.put(path)
    out = attempt(
        app_pool,
        cast.alicia,
        "update storage.objects set metadata = '{}'::jsonb where bucket_id = 'invoices' and name = %s",
        (path,),
    )
    assert not out.error and out.rowcount == 0, "no hay política de UPDATE"


def test_files_are_never_deleted_by_anyone(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    path = path_of(cast.alicia)
    objects.put(path)
    for who in ("alicia", "beto", "gina", "gus", "adan"):
        out = attempt(
            app_pool, cast[who], "delete from storage.objects where bucket_id = 'invoices' and name = %s", (path,)
        )
        assert out.error or out.rowcount == 0, who
    assert can_read(app_pool, cast.alicia, path)


# --- Leer -----------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_who_can_read_alicias_pdf_in_each_link_state(
    app_pool: Pool, cast: Cast, objects: Objects, scenario: str
) -> None:
    apply_scenario(app_pool, cast, scenario)
    alicia_pdf, beto_pdf = path_of(cast.alicia), path_of(cast.beto)
    objects.put(alicia_pdf)
    objects.put(beto_pdf)

    expected = {"alicia": True, "beto": False, "gina": scenario == "active", "gus": False, "adan": False}
    for key, allowed in expected.items():
        assert can_read(app_pool, cast[key], alicia_pdf) is allowed, f"{scenario}: {key} y el PDF de alicia"
    assert can_read(app_pool, cast.beto, beto_pdf)
    assert not can_read(app_pool, cast.alicia, beto_pdf)
    assert not can_read(app_pool, cast.gina, beto_pdf), "el gestor solo lee a quien le dio acceso"


def test_the_admin_reads_no_pdf(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    objects.put(path_of(cast.alicia))
    out = attempt(app_pool, cast.adan, "select count(*) as n from storage.objects where bucket_id = 'invoices'")
    assert not out.error and out.rows[0]["n"] == 0


def test_a_stranger_cannot_list_another_persons_folder(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    objects.put(path_of(cast.alicia))
    out = attempt(
        app_pool,
        cast.beto,
        "select name from storage.objects where bucket_id = 'invoices' and name like %s",
        (f"{cast.alicia.id}/%",),
    )
    assert not out.error and out.rows == []


def test_anon_has_no_policy_on_the_bucket(admin: Connection[DictRow]) -> None:
    row = admin.execute(
        "select count(*) as n from pg_policies where schemaname = 'storage' and tablename = 'objects' "
        "and policyname like 'invoices_objects_%%' and ('anon' = any(roles) or 'public' = any(roles))"
    ).fetchone()
    assert row == {"n": 0}
