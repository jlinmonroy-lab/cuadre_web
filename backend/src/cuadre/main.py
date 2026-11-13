"""Aplicación FastAPI de cuadre-web."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from cuadre import __version__
from cuadre.agents import get_agents_client
from cuadre.api import (
    routes_clients,
    routes_documents,
    routes_expenses,
    routes_gestor,
    routes_gestor_reads,
    routes_health,
    routes_internal,
    routes_invoices,
    routes_me,
    routes_profile,
    routes_reminders,
    routes_tax,
)
from cuadre.clients import FakeViesChecker
from cuadre.config import Settings, get_settings
from cuadre.core.auth import JwksTokenVerifier
from cuadre.core.clock import SystemClock
from cuadre.core.errors import register_error_handlers
from cuadre.core.observability import RequestContextMiddleware, configure_logging
from cuadre.core.routing import require_operation_id
from cuadre.db import open_pool
from cuadre.documents.storage import HttpStorage
from cuadre.invoicing.storage import invoice_storage
from cuadre.notifications import get_email_sender
from cuadre.profile.limits import LOGO_BUCKET, LOGO_PATH

POOL_MAX_SIZE = 10


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, include_traceback=settings.app_env == "local")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = await run_in_threadpool(open_pool, settings.database_url, name="api", max_size=POOL_MAX_SIZE)
        app.state.db_pool = pool
        try:
            yield
        finally:
            await run_in_threadpool(pool.close)

    production = settings.app_env == "production"
    app = FastAPI(
        title="Cuadre API",
        version=__version__,
        summary="API de cuadre-web: facturación, contabilidad y borradores de los modelos 303 y 130.",
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None,
        generate_unique_id_function=require_operation_id,
    )
    app.state.settings = settings
    app.state.token_verifier = JwksTokenVerifier(settings.supabase_url)
    # En producción sin AGENTS_BASE_URL (o con la configuración incompleta) esto lanza y la API no arranca (D-06).
    app.state.agents_client = get_agents_client(settings)
    app.state.storage = HttpStorage(settings.supabase_url)  # siempre con el JWT de la persona (SPEC-W-002 T2-03)
    app.state.logo_storage = HttpStorage(
        settings.supabase_url, bucket=LOGO_BUCKET, path=LOGO_PATH
    )  # bucket privado `logos`
    app.state.invoice_storage = invoice_storage(
        settings.supabase_url
    )  # bucket privado `invoices` (SPEC-W-007), siempre con el JWT de la persona
    # «hoy» en Europe/Madrid para los validadores; los tests inyectan uno fijo (SPEC-W-003 §5.4)
    app.state.clock = SystemClock()
    # VIES simulado (SPEC-W-006 D-05, RES-04): el estado se calcula, no se consulta. La costura para el real (Should) es este atributo.
    app.state.vies_checker = FakeViesChecker()
    # Correo transaccional (ADR-0008): consola en desarrollo; en producción sin proveedor real la API no arranca (DEP-05).
    app.state.email_sender = get_email_sender(settings)

    register_error_handlers(app)
    # Orden: lo último que se añade es lo más externo. CORS envuelve a RequestContext para que hasta los 500 lleven sus cabeceras.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
        allow_credentials=False,  # la API usa Authorization: Bearer, no cookies
        max_age=600,
    )

    app.include_router(routes_health.router)
    app.include_router(routes_me.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_expenses.router)
    app.include_router(routes_profile.router)
    app.include_router(routes_reminders.router)
    # `/api/clients/billing` va ANTES que `/api/clients/{client_id}`: si no, «billing» se leería como un uuid y daría 422.
    app.include_router(routes_invoices.router)
    app.include_router(routes_clients.router)
    app.include_router(routes_tax.router)
    app.include_router(routes_gestor.router)
    app.include_router(routes_gestor_reads.router)
    app.include_router(routes_internal.router)
    return app


app = create_app()
