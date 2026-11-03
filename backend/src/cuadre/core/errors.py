"""Errores de la API en `application/problem+json` (RFC 9457) con `code` estable y `detail` en español (SPEC-W-001 §5.1, T-10).

Nunca se devuelven trazas, mensajes de excepciones internas ni los datos que envió el cliente (`input` de Pydantic).
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from psycopg_pool import PoolTimeout
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

PROBLEM_JSON = "application/problem+json"


class ProblemDetails(BaseModel):
    """Forma de todo error de la API. Se declara para que aparezca en OpenAPI."""

    type: str = "about:blank"
    title: str
    status: int
    code: str
    detail: str
    request_id: str | None = None


class ValidationProblem(ProblemDetails):
    errors: list[dict[str, str]]


class ProblemError(Exception):
    """Error de negocio o de autenticación que se responde como problem+json."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str,
        *,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{code}: {title}")
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra or {}


# --- Catálogo (mensajes para personas, en español) -------------------------------------------------------------------------


def unauthenticated() -> ProblemError:
    return ProblemError(
        401,
        "unauthenticated",
        "No autenticado",
        "Tu sesión no es válida o ha caducado. Inicia sesión de nuevo.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden() -> ProblemError:
    return ProblemError(403, "forbidden", "Acceso denegado", "No tienes permiso para acceder a este recurso.")


def account_suspended() -> ProblemError:
    return ProblemError(
        403, "account_suspended", "Cuenta suspendida", "Tu cuenta está suspendida. Contacta con el administrador."
    )


def profile_missing() -> ProblemError:
    return ProblemError(
        403, "profile_missing", "Perfil no disponible", "No encontramos tu perfil. Contacta con el administrador."
    )


def auth_unavailable() -> ProblemError:
    return ProblemError(
        503,
        "auth_unavailable",
        "Servicio de autenticación no disponible",
        "No podemos comprobar tu sesión ahora mismo. Inténtalo de nuevo en unos minutos.",
        headers={"Retry-After": "30"},
    )


def database_busy() -> ProblemError:
    return ProblemError(
        503,
        "database_busy",
        "Servicio ocupado",
        "El servicio está muy ocupado ahora mismo. Inténtalo de nuevo en unos segundos.",
        headers={"Retry-After": "5"},
    )


# --- Respuestas ------------------------------------------------------------------------------------------------------------


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def problem_response(
    status: int,
    code: str,
    title: str,
    detail: str,
    *,
    request_id: str | None,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "code": code,
        "detail": detail,
        "request_id": request_id,
        **(extra or {}),
    }
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM_JSON)


def internal_error_response(request_id: str | None) -> JSONResponse:
    return problem_response(
        500,
        "internal_error",
        "Error interno",
        "Ha ocurrido un error inesperado. Si se repite, indica este identificador al soporte.",
        request_id=request_id,
    )


async def _handle_problem(request: Request, exc: ProblemError) -> JSONResponse:
    return problem_response(
        exc.status,
        exc.code,
        exc.title,
        exc.detail,
        request_id=request_id_of(request),
        headers=exc.headers,
        extra=exc.extra,
    )


async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Solo la ubicación y el mensaje: `input` puede contener datos que el cliente no querría ver reflejados ni registrados.
    errors = [{"loc": ".".join(str(part) for part in err["loc"]), "msg": str(err["msg"])} for err in exc.errors()]
    return problem_response(
        422,
        "validation_error",
        "Datos no válidos",
        "Revisa los datos enviados.",
        request_id=request_id_of(request),
        extra={"errors": errors},
    )


async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if exc.status_code == 404:
        code, title, detail = "not_found", "No encontrado", "El recurso solicitado no existe."
    elif exc.status_code == 405:
        code, title, detail = "method_not_allowed", "Método no permitido", "Este recurso no admite ese método."
    else:
        code, title, detail = "http_error", "Petición no válida", "No hemos podido procesar la petición."
    return problem_response(
        exc.status_code, code, title, detail, request_id=request_id_of(request), headers=dict(exc.headers or {})
    )


async def _handle_pool_timeout(request: Request, exc: PoolTimeout) -> JSONResponse:
    return await _handle_problem(request, database_busy())


def register_error_handlers(app: FastAPI) -> None:
    """Los errores inesperados (500) los resuelve `RequestContextMiddleware`, para que lleven `X-Request-Id` y CORS."""
    app.add_exception_handler(ProblemError, _handle_problem)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http)  # type: ignore[arg-type]
    app.add_exception_handler(PoolTimeout, _handle_pool_timeout)  # type: ignore[arg-type]
