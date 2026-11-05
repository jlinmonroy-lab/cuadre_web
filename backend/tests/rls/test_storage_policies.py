"""AC-07 · Las políticas de `storage.objects` del bucket `documents` (SPEC-W-002 §5.2, T2-06, T2-07).

Se prueban por SQL, con el mismo rol y las mismas claims que usa Storage al atender una petición: `SET LOCAL ROLE authenticated`
y `request.jwt.claims`. `test_storage_live.py` repite lo esencial contra la API real de Storage.

`storage.objects` no admite `DELETE` directo (lo prohíbe un trigger de Storage): la regla de borrado se prueba llamando a la función
que usa la política, y su cableado con la política, contra la API real en `test_storage_live.py`.
"""

import uuid
from collections.abc import Iterator

import pytest
from psycopg import Connection
from psycopg.rows import DictRow

from tests.support import Cast, Outcome, Person, Pool, advance, apply_scenario, attempt, new_document

SCENARIOS = ["baseline", "pending", "active", "revoked", "declined"]


class Objects:
    """Filas de storage.objects creadas por un test; el fixture las retira al terminar."""

    def __init__(self, admin: Connection[DictRow]) -> None:
        self.admin = admin
        self.paths: list[str] = []

    def put(self, path: str) -> None:
        """Crea el objeto como administrador de la base de datos."""
        self.admin.execute("insert into storage.objects (bucket_id, name) values ('documents', %s)", (path,))
        self.paths.append(path)

    def track(self, path: str) -> None:
        """Anota un objeto que ya creó el propio test."""
        self.paths.append(path)


@pytest.fixture
def objects(admin: Connection[DictRow]) -> Iterator[Objects]:
    store = Objects(admin)
    yield store
    if store.paths:
        # El trigger de Storage solo deja borrar a quien declara que lo hace a propósito.
        admin.execute("select set_config('storage.allow_delete_query', 'true', false)")
        admin.execute("delete from storage.objects where bucket_id = 'documents' and name = any(%s)", (store.paths,))
        admin.execute("select set_config('storage.allow_delete_query', 'false', false)")


def insert_object(pool: Pool, person: Person, path: str) -> Outcome:
    return attempt(
        pool,
        person,
        "insert into storage.objects (bucket_id, name, owner_id) values ('documents', %s, %s)",
        (path, str(person.id)),
    )


def can_read(pool: Pool, person: Person, path: str) -> bool:
    out = attempt(pool, person, "select name from storage.objects where bucket_id = 'documents' and name = %s", (path,))
    assert not out.error, out.message
    return bool(out.rows)


# --- subir ---------------------------------------------------------------------------------------------------------------------


def test_the_owner_uploads_to_the_path_the_api_reserved(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    doc = new_document(app_pool, cast.alicia)
    out = insert_object(app_pool, cast.alicia, doc.path)
    assert not out.error, out.message
    objects.track(doc.path)


def denied(out: Outcome) -> bool:
    return out.sqlstate == "42501"


def test_nothing_is_uploaded_to_a_path_the_api_did_not_reserve(app_pool: Pool, cast: Cast) -> None:
    ghost = f"{cast.alicia.id}/{uuid.uuid4()}.pdf"
    assert denied(insert_object(app_pool, cast.alicia, ghost)), "sin fila en documents"

    beto_doc = new_document(app_pool, cast.beto)
    assert denied(insert_object(app_pool, cast.alicia, beto_doc.path)), "ruta reservada por otra persona"

    own = new_document(app_pool, cast.alicia)
    assert denied(insert_object(app_pool, cast.alicia, f"{cast.alicia.id}/{uuid.uuid4()}.pdf")), "otra ruta suya"
    assert denied(insert_object(app_pool, cast.alicia, own.path.replace(".pdf", ".png"))), "otra extensión"


@pytest.mark.parametrize("who", ["beto", "gina", "gus", "adan"])
def test_nobody_else_uploads_to_alicias_reserved_path(app_pool: Pool, cast: Cast, who: str) -> None:
    apply_scenario(app_pool, cast, "active")
    doc = new_document(app_pool, cast.alicia)
    assert denied(insert_object(app_pool, cast[who], doc.path))


@pytest.mark.parametrize("state", ["processing", "review", "extraction_failed", "discarded"])
def test_a_path_can_only_be_uploaded_while_the_document_is_uploading(app_pool: Pool, cast: Cast, state: str) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    assert denied(insert_object(app_pool, cast.alicia, doc.path))


def test_a_suspended_account_uploads_nothing(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    doc = new_document(app_pool, cast.alicia)
    admin.execute("update public.profiles set status = 'suspended' where id = %s", (cast.alicia.id,))
    assert denied(insert_object(app_pool, cast.alicia, doc.path))


# --- leer ----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_who_can_read_alicias_file_in_each_link_state(
    app_pool: Pool, cast: Cast, objects: Objects, scenario: str
) -> None:
    apply_scenario(app_pool, cast, scenario)
    alicia_doc = new_document(app_pool, cast.alicia)
    beto_doc = new_document(app_pool, cast.beto)
    objects.put(alicia_doc.path)
    objects.put(beto_doc.path)

    expected = {"alicia": True, "beto": False, "gina": scenario == "active", "gus": False, "adan": False}
    for key, allowed in expected.items():
        assert can_read(app_pool, cast[key], alicia_doc.path) is allowed, f"{scenario}: {key} y el archivo de alicia"
    assert can_read(app_pool, cast.beto, beto_doc.path)
    assert not can_read(app_pool, cast.alicia, beto_doc.path)
    assert not can_read(app_pool, cast.gina, beto_doc.path), "el gestor solo lee a quien le dio acceso"


def test_a_stranger_cannot_list_another_persons_folder(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    doc = new_document(app_pool, cast.alicia)
    objects.put(doc.path)
    out = attempt(
        app_pool,
        cast.beto,
        "select name from storage.objects where bucket_id = 'documents' and name like %s",
        (f"{cast.alicia.id}/%",),
    )
    assert not out.error and out.rows == []


# --- sobrescribir y borrar -------------------------------------------------------------------------------------------------------


def test_files_are_never_overwritten(app_pool: Pool, cast: Cast, objects: Objects) -> None:
    doc = new_document(app_pool, cast.alicia)
    objects.put(doc.path)
    for column, value in (("name", f"{cast.alicia.id}/{uuid.uuid4()}.pdf"), ("metadata", '{"size": 1}')):
        out = attempt(
            app_pool,
            cast.alicia,
            f"update storage.objects set {column} = %s where bucket_id = 'documents' and name = %s",
            (value, doc.path),
        )
        assert out.blocked, f"alicia pudo cambiar {column}"


def can_delete(pool: Pool, person: Person, path: str) -> bool:
    out = attempt(pool, person, "select private.document_can_delete(%s) as ok", (path,))
    assert not out.error, out.message
    return out.rows[0]["ok"]


@pytest.mark.parametrize("state", ["uploading", "processing", "review", "extraction_failed", "discarded"])
def test_the_owner_may_delete_until_the_document_is_registered(app_pool: Pool, cast: Cast, state: str) -> None:
    doc = advance(app_pool, cast.alicia, new_document(app_pool, cast.alicia), state)
    assert can_delete(app_pool, cast.alicia, doc.path)
    for key in ("beto", "gina", "gus", "adan"):
        assert not can_delete(app_pool, cast[key], doc.path), key


def test_a_registered_document_keeps_its_file(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    path_id = uuid.uuid4()
    path = f"{cast.alicia.id}/{path_id}.pdf"
    admin.execute(
        "insert into public.documents (id, owner_id, status, source, original_filename, mime_type, size_bytes, storage_path, extraction) "
        "values (%s, %s, 'registered', 'file', 'f.pdf', 'application/pdf', 10, %s, '{}')",
        (path_id, cast.alicia.id, path),
    )
    assert not can_delete(app_pool, cast.alicia, path)


def test_an_orphan_file_without_a_row_can_be_deleted_by_its_owner_only(app_pool: Pool, cast: Cast) -> None:
    orphan = f"{cast.alicia.id}/{uuid.uuid4()}.pdf"
    assert can_delete(app_pool, cast.alicia, orphan)
    assert not can_delete(app_pool, cast.beto, orphan)


# --- rutas raras ----------------------------------------------------------------------------------------------------------------

WEIRD_NAMES = [
    "",
    "x",
    "x/y",
    "not-a-uuid/file.pdf",
    "/file.pdf",
    "../../etc/passwd",
    "a" * 300,
    "%s",  # el uuid de alicia a secas, sin archivo
    "%s/",  # carpeta sin archivo
    "%s/a/b.pdf",  # una carpeta de más
]


@pytest.mark.parametrize("function", ["document_can_upload", "document_can_read", "document_can_delete"])
def test_malformed_paths_are_denied_not_errors(app_pool: Pool, cast: Cast, function: str) -> None:
    names = [n.replace("%s", str(cast.alicia.id)) for n in WEIRD_NAMES] + [f"{str(cast.alicia.id).upper()}/f.pdf"]
    for name in names:
        out = attempt(app_pool, cast.alicia, f"select private.{function}(%s) as ok", (name,))
        assert not out.error, f"{function}({name!r}) lanzó {out.message}"
        assert out.rows[0]["ok"] is False, f"{function}({name!r}) devolvió {out.rows[0]['ok']}"


def test_the_helpers_are_not_reachable_by_anon(app_pool: Pool) -> None:
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege), app_pool.connection() as conn:
        conn.execute("SET LOCAL ROLE anon")
        conn.execute("select private.document_can_read('x/y')")
