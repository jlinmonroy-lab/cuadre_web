"""Aplicación FastAPI de cuadre-web."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from cuadre import __version__
from cuadre.api import routes_health, routes_me
from cuadre.config import Settings, get_settings
from cuadre.core.auth import JwksTokenVerifier
from cuadre.core.errors import register_error_handlers
from cuadre.core.observability import RequestContextMiddleware, configure_logging
from cuadre.core.routing import require_operation_id
from cuadre.db import open_pool

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
    return app


app = create_app()
