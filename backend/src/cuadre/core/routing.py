"""Todas las rutas declaran `operation_id` explícito (SPEC-W-001 T-11, ADR-0011).

El cliente TypeScript se genera desde `openapi.json` y sus funciones se llaman como el `operation_id`: si lo dejara FastAPI,
cambiar una ruta de sitio renombraría el cliente. Por eso un `operation_id` ausente es un error AL DEFINIR la ruta.
"""

from collections.abc import Sequence

from fastapi import APIRouter
from fastapi.routing import APIRoute


def require_operation_id(route: APIRoute) -> str:
    raise RuntimeError(
        f"La ruta {sorted(route.methods or [])} {route.path} no declara operation_id. "
        "Usa operation_id='verbo_objeto' (por ejemplo get_me, issue_invoice)."
    )


def new_router(*, tags: Sequence[str]) -> APIRouter:
    """Único modo de crear un `APIRouter` en `cuadre.api` (lo vigila un test)."""
    return APIRouter(tags=list(tags), generate_unique_id_function=require_operation_id)
