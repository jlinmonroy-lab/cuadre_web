"""AC-17 · Solo el rol `usuario` usa el perfil; cada persona ve lo suyo."""

import pytest

from tests.profile.conftest import JPEG, VALID, Api

ROUTES = [
    ("GET", "/api/profile", None),
    ("PUT", "/api/profile", {}),
    ("POST", "/api/profile/logo", {"mime_type": "image/png", "size_bytes": 10}),
    ("POST", "/api/profile/logo/00000000-0000-4000-8000-000000000000/complete", None),
    ("GET", "/api/profile/logo", None),
    ("DELETE", "/api/profile/logo", None),
    ("GET", "/api/invoice-series", None),
    ("POST", "/api/invoice-series", {"code": "X"}),
    ("PATCH", "/api/invoice-series/00000000-0000-4000-8000-000000000000", {"description": "x"}),
    ("PUT", "/api/invoice-series/00000000-0000-4000-8000-000000000000/default", None),
]


@pytest.mark.parametrize("who", ["gina", "adan"])
@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_ac17_managers_and_admins_get_403(api: Api, who: str, method: str, url: str, body: dict | None) -> None:
    kwargs = {} if body is None else {"json": body}
    response = api.request(method, url, api.cast[who], **kwargs)
    assert (response.status_code, response.json()["code"]) == (403, "forbidden")


@pytest.mark.parametrize(("method", "url", "body"), ROUTES)
def test_every_route_needs_a_session(api: Api, method: str, url: str, body: dict | None) -> None:
    kwargs = {} if body is None else {"json": body}
    assert api.client.request(method, url, **kwargs).status_code == 401


def test_ac17_each_user_sees_only_their_own_profile_series_and_logo(api: Api) -> None:
    api.save(api.cast.alicia, **VALID)
    api.complete(api.cast.alicia, api.logo(api.cast.alicia))
    beto = api.profile(api.cast.beto).json()
    assert (beto["legal_name"], beto["has_logo"]) == (None, False)
    assert api.series(api.cast.beto) == []
    assert api.request("GET", "/api/profile/logo", api.cast.beto).status_code == 404


def test_ac17_the_logo_is_stored_in_the_callers_own_folder(api: Api) -> None:
    upload_id = api.logo(api.cast.alicia, data=JPEG, mime="image/jpeg")
    (path,) = api.storage.objects
    assert path == f"{api.cast.alicia.id}/{upload_id}.jpg"
    assert all(call.path.startswith(str(api.cast.alicia.id)) for call in api.storage.calls)
