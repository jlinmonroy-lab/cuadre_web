"""AC-01, AC-03, AC-11, AC-12, AC-13, AC-14 a nivel de base de datos · estados, límites y reglas de `documents` (SPEC-W-002 §5.1-§5.3).

Las rutas de la API llegan en el hito 3; aquí se prueban las funciones `app.*` y el trigger como la red de seguridad que son:
varias comprobaciones escriben directamente como dueño de la base de datos para demostrar que la tabla no admite lo ilegal venga
de donde venga.
"""

import json
import threading
import time
import uuid
from typing import Any

import psycopg
import pytest
from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from cuadre.db import user_transaction
from tests.support import GOOD_EXTRACTION, Cast, Doc, Pool, advance, attempt, call, new_document

STATES = ["uploading", "processing", "review", "extraction_failed", "discarded", "registered"]
LIVE_STATES = ["uploading", "processing", "review", "extraction_failed"]


def row(admin: Connection[DictRow], doc: Doc) -> dict[str, Any]:
    found = admin.execute("select * from public.documents where id = %s", (doc.id,)).fetchone()
    assert found is not None
    return found


def log_of(admin: Connection[DictRow], cast: Cast) -> list[dict[str, Any]]:
    return admin.execute(
        "select action, category, actor_id, actor_role, owner_id, entity_type, entity_id, metadata "
        "from public.activity_log where owner_id = %s and action like 'document.%%' order by id",
        (cast.alicia.id,),
    ).fetchall()


def make(pool: Pool, cast: Cast, state: str) -> Doc:
    return advance(pool, cast.alicia, new_document(pool, cast.alicia), state)


def age(admin: Connection[DictRow], doc: Doc, seconds: int) -> None:
    """Envejece la fila (el trigger respeta un `updated_at` fijado a propósito)."""
    admin.execute(
        "update public.documents set updated_at = now() - make_interval(secs => %s) where id = %s", (seconds, doc.id)
    )


# --- camino normal ------------------------------------------------------------------------------------------------------------


def test_the_normal_path_and_its_activity_log(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-01."""
    doc = new_document(app_pool, cast.alicia, filename="secreto-12345678Z.pdf", size=4096, source="camera")
    created = row(admin, doc)
    assert created["status"] == "uploading" and created["storage_path"] == f"{cast.alicia.id}/{doc.id}.pdf"
    assert doc.path == created["storage_path"]
    assert created["uploaded_at"] is None and created["extraction"] is None and created["injection_suspected"] is False
    assert log_of(admin, cast) == [], "reservar un documento no registra nada"

    assert not call(app_pool, cast.alicia, "mark_document_uploaded", doc.id).error
    processing = row(admin, doc)
    assert processing["status"] == "processing" and processing["uploaded_at"] is not None

    extraction = {**GOOD_EXTRACTION, "supplier_name": "Proveedor con NIF 12345678Z"}
    out = attempt(
        app_pool,
        cast.alicia,
        "select app.record_extraction(%s, %s, true, 'trace-1', 0.012345)",
        (doc.id, Jsonb(extraction)),
    )
    assert not out.error, out.message
    reviewed = row(admin, doc)
    assert reviewed["status"] == "review" and reviewed["extraction"] == extraction
    assert reviewed["injection_suspected"] is True and reviewed["agent_trace_id"] == "trace-1"
    assert str(reviewed["agent_cost_eur"]) == "0.012345" and reviewed["extracted_at"] is not None

    entries = log_of(admin, cast)
    assert [e["action"] for e in entries] == ["document.uploaded", "document.extracted"]
    for entry in entries:
        assert entry["category"] == "data" and entry["actor_role"] == "usuario" and entry["actor_id"] == cast.alicia.id
        assert entry["entity_type"] == "document" and entry["entity_id"] == str(doc.id)
    assert entries[0]["metadata"] == {
        "document_id": str(doc.id),
        "mime_type": "application/pdf",
        "size_bytes": 4096,
        "source": "camera",
    }
    assert entries[1]["metadata"] == {"document_id": str(doc.id), "injection_suspected": True, "doubtful_count": 1}
    everything = json.dumps([e["metadata"] for e in entries])
    for secret in ("secreto", "12345678Z", "Proveedor", "12100", "factura"):
        assert secret not in everything, f"el registro de actividad contiene «{secret}»"


def test_failure_then_retry_with_the_same_id(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    doc = make(app_pool, cast, "extraction_failed")
    failed = row(admin, doc)
    assert failed["status"] == "extraction_failed" and failed["error_code"] == "unreadable"

    assert not call(app_pool, cast.alicia, "retry_document", doc.id).error
    retried = row(admin, doc)
    assert retried["status"] == "processing" and retried["error_code"] is None and retried["id"] == doc.id

    out = attempt(
        app_pool,
        cast.alicia,
        "select app.record_extraction(%s, %s, false, null, null)",
        (doc.id, Jsonb(GOOD_EXTRACTION)),
    )
    assert not out.error, out.message
    assert row(admin, doc)["status"] == "review"
    entries = log_of(admin, cast)
    assert [e["action"] for e in entries] == ["document.uploaded", "document.extraction_failed", "document.extracted"]
    assert entries[1]["metadata"] == {"document_id": str(doc.id), "error_code": "unreadable"}


# --- transiciones ----------------------------------------------------------------------------------------------------------------

ARGS = {
    "mark_document_uploaded": lambda d: (d,),
    "record_extraction": lambda d: (d, Jsonb(GOOD_EXTRACTION), False, None, None),
    "fail_extraction": lambda d: (d, "unreadable"),
    "retry_document": lambda d: (d,),
    "save_document_review": lambda d: (d, Jsonb({"total_cents": 1})),
    "discard_document": lambda d: (d,),
}

# Lo que cada estado admite: todo lo demás debe fallar con document_wrong_state.
ALLOWED = {
    "uploading": {"mark_document_uploaded", "discard_document"},
    "processing": {"record_extraction", "fail_extraction", "discard_document"},
    "review": {"save_document_review", "discard_document"},
    "extraction_failed": {"retry_document", "save_document_review", "discard_document"},
    "discarded": set(),
    "registered": set(),  # solo vuelve a revisión anulando su gasto (SPEC-W-003): ninguna función de documentos lo toca
}
ILLEGAL = [(s, f) for s in STATES for f in ARGS if f not in ALLOWED[s]]


@pytest.mark.parametrize(("state", "function"), ILLEGAL)
def test_every_illegal_move_is_refused_and_changes_nothing(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str, function: str
) -> None:
    doc = make(app_pool, cast, state)
    before = row(admin, doc)
    logged = len(log_of(admin, cast))

    args = ARGS[function](doc.id)
    out = attempt(app_pool, cast.alicia, f"select app.{function}({', '.join(['%s'] * len(args))})", args)

    assert out.sqlstate == "P0001" and "document_wrong_state" in (out.message or ""), out.message
    assert row(admin, doc) == before
    assert len(log_of(admin, cast)) == logged


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        (
            "update public.documents set status = 'review', extraction = '{}' where id = %s",
            "document_invalid_transition",
        ),
        (
            "update public.documents set status = 'extraction_failed', error_code = 'timeout' where id = %s",
            "document_invalid_transition",
        ),
        ("update public.documents set status = 'registered' where id = %s", "document_invalid_transition"),
        (
            "update public.documents set error_code = 'timeout' where id = %s",
            "document_invalid_transition",
        ),  # uploading sin cambio
        ("update public.documents set owner_id = gen_random_uuid() where id = %s", "document_immutable_column"),
        ("update public.documents set storage_path = 'otra' where id = %s", "document_immutable_column"),
        ("update public.documents set mime_type = 'image/png' where id = %s", "document_immutable_column"),
        ("update public.documents set size_bytes = 1 where id = %s", "document_immutable_column"),
        ("update public.documents set original_filename = 'otro.pdf' where id = %s", "document_immutable_column"),
        ("update public.documents set source = 'camera' where id = %s", "document_immutable_column"),
        (
            "update public.documents set created_at = now() - interval '1 day' where id = %s",
            "document_immutable_column",
        ),
    ],
)
def test_the_trigger_refuses_what_the_functions_would_never_do(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, statement: str, message: str
) -> None:
    doc = make(app_pool, cast, "uploading")
    before = row(admin, doc)
    with pytest.raises(psycopg.errors.RaiseException, match=message):
        admin.execute(statement, (doc.id,))
    assert row(admin, doc) == before


@pytest.mark.parametrize(
    "statement",
    [
        "update public.documents set status = 'processing' where id = %s",
        "update public.documents set status = 'uploading' where id = %s",
        "update public.documents set review = '{}' where id = %s",
    ],
)
def test_discarded_is_final(app_pool: Pool, admin: Connection[DictRow], cast: Cast, statement: str) -> None:
    doc = make(app_pool, cast, "discarded")
    with pytest.raises(psycopg.errors.RaiseException, match="document_invalid_transition"):
        admin.execute(statement, (doc.id,))


@pytest.mark.parametrize(
    "statement",
    [
        "update public.documents set extraction = '{\"total_cents\": 1}' where id = %s",
        "update public.documents set injection_suspected = not injection_suspected where id = %s",
        "update public.documents set agent_trace_id = 'otra' where id = %s",
        "update public.documents set agent_cost_eur = 9 where id = %s",
        "update public.documents set status = 'discarded', extraction = '{}' where id = %s",
    ],
)
def test_the_original_reading_is_frozen_once_it_exists(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, statement: str
) -> None:
    """AC-14 · guardar correcciones (o descartar) no reescribe lo que leyó el agente."""
    doc = make(app_pool, cast, "review")
    before = row(admin, doc)
    with pytest.raises(psycopg.errors.RaiseException, match="document_extraction_frozen"):
        admin.execute(statement, (doc.id,))
    assert row(admin, doc) == before


def test_updated_at_follows_every_change_unless_it_is_set_on_purpose(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    doc = make(app_pool, cast, "review")
    first = row(admin, doc)["updated_at"]
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb({"total_cents": 5})).error
    second = row(admin, doc)["updated_at"]
    assert second > first
    age(admin, doc, 500)
    assert row(admin, doc)["updated_at"] < second


# --- CHECK de la tabla ------------------------------------------------------------------------------------------------------------

INSERT = (
    "insert into public.documents (id, owner_id, status, source, original_filename, mime_type, size_bytes, storage_path, "
    "extraction, error_code) values (%(id)s, %(owner)s, %(status)s, 'file', 'f.pdf', %(mime)s, %(size)s, %(path)s, %(ext)s, %(code)s)"
)


def insert_params(cast: Cast, **overrides: Any) -> dict[str, Any]:
    doc_id = uuid.uuid4()
    base = {
        "id": doc_id,
        "owner": cast.alicia.id,
        "status": "uploading",
        "mime": "application/pdf",
        "size": 10,
        "path": f"{cast.alicia.id}/{doc_id}.pdf",
        "ext": None,
        "code": None,
    }
    return {**base, **overrides}


def test_a_valid_insert_works_so_the_other_cases_prove_something(admin: Connection[DictRow], cast: Cast) -> None:
    admin.execute(INSERT, insert_params(cast))


@pytest.mark.parametrize(
    "overrides",
    [
        {"path": "otra/ruta.pdf"},
        {"mime": "image/png"},  # la ruta dice .pdf
        {"mime": "text/plain", "path": "x"},
        {"size": 0},
        {"size": 15728641},
        {"status": "review"},  # sin lectura
        {"status": "extraction_failed"},  # sin motivo
        {"code": "inventado"},
    ],
)
def test_the_table_rejects_malformed_rows(admin: Connection[DictRow], cast: Cast, overrides: dict[str, Any]) -> None:
    params = insert_params(cast, **overrides)
    with pytest.raises(psycopg.errors.CheckViolation):
        admin.execute(INSERT, params)


def test_the_path_never_carries_the_file_name(app_pool: Pool, cast: Cast) -> None:
    doc = new_document(app_pool, cast.alicia, filename="Mi factura de Juan García.pdf")
    assert "Juan" not in doc.path and doc.path.count("/") == 1
    assert doc.path == f"{cast.alicia.id}/{doc.id}.pdf"


@pytest.mark.parametrize(
    ("mime", "ext"),
    [
        ("application/pdf", "pdf"),
        ("image/jpeg", "jpg"),
        ("image/png", "png"),
        ("image/heic", "heic"),
        ("image/webp", "webp"),
    ],
)
def test_each_type_gets_its_extension(app_pool: Pool, cast: Cast, mime: str, ext: str) -> None:
    doc = new_document(app_pool, cast.alicia, mime=mime)
    assert doc.path.endswith(f"/{doc.id}.{ext}")


def test_an_unsupported_type_is_refused_by_the_table(app_pool: Pool, cast: Cast) -> None:
    out = attempt(app_pool, cast.alicia, "select * from app.create_document('f.txt', 'text/plain', 10, 'file')")
    assert out.sqlstate == "23514"


VALID_AMOUNTS: list[Any] = [
    {},
    {"total_cents": None},
    {"total_cents": -500, "tax_breakdown": [], "withholding": None},
    {"total_cents": 12100, "tax_breakdown": [{"vat_rate": "21", "base_cents": 10000, "vat_cents": 2100}]},
    {"withholding": {"rate": "15", "amount_cents": 1800}},
    GOOD_EXTRACTION,
]
INVALID_AMOUNTS: list[Any] = [
    {"total_cents": 12.5},
    {"total_cents": 12.0},
    {"total_cents": "120.00"},
    {"total_cents": True},
    {"total_cents": 10**16},
    {"tax_breakdown": [{"base_cents": 100.5, "vat_cents": 21}]},
    {"tax_breakdown": [{"base_cents": 100, "vat_cents": "21"}]},
    {"tax_breakdown": [{"base_cents": 100, "vat_cents": 21}, {"base_cents": 1.5}]},
    {"withholding": {"amount_cents": "1800"}},
    {"withholding": {"amount_cents": 18.5}},
    [],
    "texto",
    1,
]


@pytest.mark.parametrize("amounts", VALID_AMOUNTS)
def test_whole_cents_are_accepted_in_the_reading_and_in_the_review(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, amounts: Any
) -> None:
    doc = make(app_pool, cast, "processing")
    out = attempt(
        app_pool, cast.alicia, "select app.record_extraction(%s, %s, false, null, null)", (doc.id, Jsonb(amounts))
    )
    assert not out.error, out.message
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb(amounts)).error


@pytest.mark.parametrize("amounts", INVALID_AMOUNTS)
def test_anything_but_whole_cents_is_refused_and_nothing_is_saved(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, amounts: Any
) -> None:
    """AC-03 · RES-02 también en la base: un importe mal formado no entra ni en la lectura ni en las correcciones."""
    doc = make(app_pool, cast, "processing")
    out = attempt(
        app_pool, cast.alicia, "select app.record_extraction(%s, %s, false, null, null)", (doc.id, Jsonb(amounts))
    )
    assert out.sqlstate == "23514", out.message
    after = row(admin, doc)
    assert after["status"] == "processing" and after["extraction"] is None

    reviewed = make(app_pool, cast, "review")
    bad = call(app_pool, cast.alicia, "save_document_review", reviewed.id, Jsonb(amounts))
    assert bad.sqlstate == "23514", bad.message
    assert row(admin, reviewed)["review"] is None


# --- límites y caducidad ----------------------------------------------------------------------------------------------------------


def test_at_most_five_simultaneous_reads_per_person(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    """AC-12."""
    reading = [make(app_pool, cast, "processing") for _ in range(5)]
    before = admin.execute(
        "select count(*) as n from public.documents where owner_id = %s", (cast.alicia.id,)
    ).fetchone()

    out = attempt(app_pool, cast.alicia, "select * from app.create_document('f.pdf', 'application/pdf', 10, 'file')")
    assert out.sqlstate == "P0001" and "too_many_processing" in (out.message or "")
    after = admin.execute(
        "select count(*) as n from public.documents where owner_id = %s", (cast.alicia.id,)
    ).fetchone()
    assert before == after, "no se crea ninguna fila"

    other = new_document(app_pool, cast.beto)  # el límite es por persona
    assert not call(app_pool, cast.beto, "mark_document_uploaded", other.id).error

    assert not call(app_pool, cast.alicia, "discard_document", reading[0].id).error
    assert not attempt(
        app_pool, cast.alicia, "select * from app.create_document('f.pdf', 'application/pdf', 10, 'file')"
    ).error


def test_the_limit_is_also_enforced_where_the_reading_starts(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """Se pueden reservar muchas subidas; lo que no se puede es leer más de cinco a la vez."""
    docs = [new_document(app_pool, cast.alicia) for _ in range(6)]
    for doc in docs[:5]:
        assert not call(app_pool, cast.alicia, "mark_document_uploaded", doc.id).error

    out = call(app_pool, cast.alicia, "mark_document_uploaded", docs[5].id)
    assert out.sqlstate == "P0001" and "too_many_processing" in (out.message or "")
    assert row(admin, docs[5])["status"] == "uploading"


def test_two_simultaneous_requests_cannot_both_take_the_last_place(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """El cerrojo por persona: la segunda petición espera a que la primera confirme y entonces ya no cabe."""
    for _ in range(4):
        make(app_pool, cast, "processing")
    first, second = new_document(app_pool, cast.alicia), new_document(app_pool, cast.alicia)
    outcome: dict[str, Any] = {}

    def later() -> None:
        outcome["second"] = call(app_pool, cast.alicia, "mark_document_uploaded", second.id)

    waiter = threading.Thread(target=later)
    with user_transaction(app_pool, cast.alicia.id) as conn:
        conn.execute("select app.mark_document_uploaded(%s)", (first.id,))  # aún sin confirmar
        waiter.start()
        time.sleep(1)
        still_waiting = waiter.is_alive()  # sin el cerrojo ya habría terminado: ve 4 lecturas, no 5
    waiter.join(timeout=15)

    assert still_waiting, "la segunda petición no esperó a la primera"
    assert outcome["second"].sqlstate == "P0001" and "too_many_processing" in (outcome["second"].message or "")
    reading = admin.execute(
        "select count(*) as n from public.documents where owner_id = %s and status = 'processing'", (cast.alicia.id,)
    ).fetchone()
    assert reading == {"n": 5}
    assert row(admin, second)["status"] == "uploading"


def test_a_retry_also_counts_against_the_limit(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    failed = make(app_pool, cast, "extraction_failed")
    for _ in range(5):
        make(app_pool, cast, "processing")
    out = call(app_pool, cast.alicia, "retry_document", failed.id)
    assert out.sqlstate == "P0001" and "too_many_processing" in (out.message or "")
    assert row(admin, failed)["status"] == "extraction_failed"


def test_expired_reads_do_not_count_against_the_limit(app_pool: Pool, admin: Connection[DictRow], cast: Cast) -> None:
    reading = [make(app_pool, cast, "processing") for _ in range(5)]
    sql = "select * from app.create_document('f.pdf', 'application/pdf', 10, 'file')"
    assert attempt(app_pool, cast.alicia, sql).sqlstate == "P0001"

    age(admin, reading[0], 121)  # una lectura interrumpida deja de ocupar sitio
    assert not attempt(app_pool, cast.alicia, sql).error


def test_a_stale_processing_document_can_be_read_again_a_fresh_one_cannot(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """AC-11."""
    doc = make(app_pool, cast, "processing")
    assert call(app_pool, cast.alicia, "retry_document", doc.id).sqlstate == "P0001", "recién empezada: no"

    age(admin, doc, 119)
    assert call(app_pool, cast.alicia, "retry_document", doc.id).sqlstate == "P0001", "119 s: aún no"

    age(admin, doc, 121)
    stale = row(admin, doc)["updated_at"]
    assert not call(app_pool, cast.alicia, "retry_document", doc.id).error
    again = row(admin, doc)
    assert again["status"] == "processing" and again["id"] == doc.id and again["updated_at"] > stale


# --- descartar y corregir ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("state", LIVE_STATES)
def test_discarding_from_every_live_state(app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str) -> None:
    """AC-13."""
    doc = make(app_pool, cast, state)
    assert not call(app_pool, cast.alicia, "discard_document", doc.id).error
    assert row(admin, doc)["status"] == "discarded"
    last = log_of(admin, cast)[-1]
    assert last["action"] == "document.discarded"
    assert last["metadata"] == {"document_id": str(doc.id), "from_status": state}

    again = call(app_pool, cast.alicia, "discard_document", doc.id)
    assert again.sqlstate == "P0001" and "document_wrong_state" in (again.message or "")


@pytest.mark.parametrize("state", ["review", "extraction_failed"])
def test_saving_a_review_keeps_the_original_reading(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast, state: str
) -> None:
    """AC-14."""
    doc = make(app_pool, cast, state)
    before = row(admin, doc)

    corrections = {"supplier_tax_id": "TEST-0001", "total_cents": 12100}
    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb(corrections)).error
    after = row(admin, doc)
    assert after["review"] == corrections
    assert after["status"] == state
    for column in ("extraction", "injection_suspected", "agent_trace_id", "agent_cost_eur", "error_code"):
        assert after[column] == before[column], column

    assert not call(app_pool, cast.alicia, "save_document_review", doc.id, Jsonb({"total_cents": 7})).error
    assert row(admin, doc)["review"] == {"total_cents": 7}, "guardar de nuevo sustituye las correcciones"


def test_a_review_cannot_be_cleared_with_null(app_pool: Pool, cast: Cast) -> None:
    doc = make(app_pool, cast, "review")
    out = attempt(app_pool, cast.alicia, "select app.save_document_review(%s, null)", (doc.id,))
    assert out.sqlstate == "P0001" and "invalid_review" in (out.message or "")


def test_records_are_removed_with_the_account_but_the_log_stays(
    app_pool: Pool, admin: Connection[DictRow], cast: Cast
) -> None:
    """La FK en cascada deja la puerta abierta a CONF-004 (retención); el registro de actividad no tiene claves foráneas."""
    doc = make(app_pool, cast, "review")
    logged = len(log_of(admin, cast))
    admin.execute("delete from auth.users where id = %s", (cast.alicia.id,))
    assert admin.execute("select 1 from public.documents where id = %s", (doc.id,)).fetchone() is None
    assert len(log_of(admin, cast)) == logged
