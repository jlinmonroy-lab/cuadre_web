"""T-07 · La Data API (PostgREST) está desactivada y las tablas nuevas no se exponen por defecto (ADR-0004)."""

import tomllib

from tests.rules.paths import REPO


def test_postgrest_is_disabled_and_new_tables_are_not_auto_exposed() -> None:
    config = tomllib.loads((REPO / "supabase" / "config.toml").read_text(encoding="utf-8"))
    assert config["api"]["enabled"] is False, "el único camino a los datos es el backend FastAPI"
    assert config["api"]["auto_expose_new_tables"] is False, "los GRANT son explícitos en cada migración"


def test_email_confirmation_and_password_length_match_production() -> None:
    """T-16."""
    auth = tomllib.loads((REPO / "supabase" / "config.toml").read_text(encoding="utf-8"))["auth"]
    assert auth["email"]["enable_confirmations"] is True
    assert auth["minimum_password_length"] >= 10


def test_the_signing_keys_file_is_never_tracked() -> None:
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "supabase/signing_keys.json" in ignored
