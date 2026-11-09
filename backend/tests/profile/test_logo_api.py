"""AC-14 a AC-16 · El logo por la API: subida firmada, comprobaciones, sustitución y borrado. Storage es un doble en memoria."""

from tests.documents.fakes import FakeStorage
from tests.profile.conftest import JPEG, PNG, VALID, WEBP, Api


def test_ac14_upload_complete_and_read(api: Api, storage: FakeStorage) -> None:
    alicia = api.cast.alicia
    upload_id = api.logo(alicia)
    done = api.complete(alicia, upload_id)
    assert done.status_code == 200, done.text
    assert done.json()["has_logo"] is True
    shown = api.request("GET", "/api/profile/logo", alicia)
    assert shown.status_code == 200
    assert shown.json()["expires_in"] == 60
    assert storage.read_expiries == [60]
    assert all(call.token == api.signer.token(alicia) or call.token for call in storage.calls)


def test_ac14_a_new_logo_deletes_the_previous_object(api: Api, storage: FakeStorage) -> None:
    alicia = api.cast.alicia
    first = api.logo(alicia)
    api.complete(alicia, first)
    second = api.logo(alicia, data=JPEG, mime="image/jpeg")
    assert api.complete(alicia, second).status_code == 200
    assert sorted(storage.objects) == [f"{alicia.id}/{second}.jpg"]


def test_ac14_webp_is_accepted(api: Api) -> None:
    assert api.complete(api.cast.alicia, api.logo(api.cast.alicia, data=WEBP, mime="image/webp")).status_code == 200


def test_ac15_unsupported_type_and_too_large_are_rejected_before_signing(api: Api, storage: FakeStorage) -> None:
    for mime in ("image/svg+xml", "image/gif", "text/plain"):
        response = api.request("POST", "/api/profile/logo", api.cast.alicia, json={"mime_type": mime, "size_bytes": 10})
        assert (response.status_code, response.json()["code"]) == (415, "logo_unsupported_type")
    big = api.request(
        "POST", "/api/profile/logo", api.cast.alicia, json={"mime_type": "image/png", "size_bytes": 1_048_577}
    )
    assert (big.status_code, big.json()["code"]) == (413, "logo_too_large")
    exact = api.request(
        "POST", "/api/profile/logo", api.cast.alicia, json={"mime_type": "image/png", "size_bytes": 1_048_576}
    )
    assert exact.status_code == 201
    zero = api.request("POST", "/api/profile/logo", api.cast.alicia, json={"mime_type": "image/png", "size_bytes": 0})
    assert (zero.status_code, zero.json()["code"]) == (422, "logo_invalid")
    assert len(storage.operations("sign_upload")) == 1  # solo la de 1 MiB exacto


def test_ac15_text_with_a_png_name_is_rejected_and_deleted(api: Api, storage: FakeStorage) -> None:
    alicia = api.cast.alicia
    upload_id = api.logo(alicia, data=b"esto no es una imagen png")
    response = api.complete(alicia, upload_id)
    assert (response.status_code, response.json()["code"]) == (422, "logo_invalid")
    assert api.profile(alicia).json()["has_logo"] is False
    assert storage.objects == {}


def test_ac15_a_type_that_storage_registered_differently_is_rejected(api: Api) -> None:
    upload_id = api.logo(api.cast.alicia, registered="text/plain")
    assert api.complete(api.cast.alicia, upload_id).json()["code"] == "logo_invalid"


def test_ac15_a_declared_size_that_was_exceeded_is_rejected(api: Api) -> None:
    upload_id = api.logo(api.cast.alicia, data=PNG + b"\x00" * 1_048_576, declared=100)
    assert api.complete(api.cast.alicia, upload_id).json()["code"] == "logo_invalid"


def test_ac15_completing_without_having_uploaded_is_a_422(api: Api) -> None:
    response = api.complete(api.cast.alicia, "00000000-0000-4000-8000-000000000000")
    assert (response.status_code, response.json()["code"]) == (422, "logo_invalid")
    assert api.profile(api.cast.alicia).json()["has_logo"] is False


def test_ac15_someone_elses_upload_id_finds_nothing(api: Api) -> None:
    upload_id = api.logo(api.cast.alicia)
    assert api.complete(api.cast.beto, upload_id).json()["code"] == "logo_invalid"


def test_ac16_delete_is_idempotent_and_removes_the_object(api: Api, storage: FakeStorage) -> None:
    alicia = api.cast.alicia
    assert api.request("DELETE", "/api/profile/logo", alicia).status_code == 204  # sin logo
    api.complete(alicia, api.logo(alicia))
    assert api.request("DELETE", "/api/profile/logo", alicia).status_code == 204
    assert api.profile(alicia).json()["has_logo"] is False
    assert storage.objects == {}
    missing = api.request("GET", "/api/profile/logo", alicia)
    assert (missing.status_code, missing.json()["code"]) == (404, "logo_not_found")
    assert api.request("DELETE", "/api/profile/logo", alicia).status_code == 204


def test_saving_the_profile_does_not_touch_the_logo(api: Api) -> None:
    api.complete(api.cast.alicia, api.logo(api.cast.alicia))
    assert api.save(api.cast.alicia, **VALID).json()["has_logo"] is True
