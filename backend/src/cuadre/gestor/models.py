"""Modelos de la API del acceso del gestor (SPEC-W-010 §5.1 y §5.3). De ellos sale el cliente TypeScript."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cuadre.expenses.models import Expense
from cuadre.profile.models import InvoiceSeries, Profile

AccessStatus = Literal["pending", "active", "revoked", "declined", "expired"]


class InviteInput(BaseModel):
    """El correo del gestor. Se recorta y pasa a minúsculas en la base; su formato lo valida la función `app.invite_gestor_access`."""

    email: str = Field(max_length=320, description="Correo electrónico del gestor al que se invita")


class GestorAccess(BaseModel):
    """Un acceso (o invitación) que el autónomo ha dado a un gestor."""

    id: UUID
    gestor_email: str
    status: AccessStatus = Field(
        description="`expired` es una invitación pendiente cuya fecha de caducidad ya pasó (no es un estado de la base de datos)"
    )
    invited_at: datetime
    expires_at: datetime = Field(description="Caducidad de la invitación pendiente (14 días desde que se envió)")


class InvitedAccess(GestorAccess):
    """El acceso recién creado. `email_sent` es `false` si el correo no se pudo entregar: la invitación existe igualmente y queda pendiente."""

    email_sent: bool


class GestorInvitation(BaseModel):
    """Una invitación pendiente dirigida al gestor que pregunta."""

    id: UUID
    owner_name: str = Field(description="Nombre de quien invita")
    invited_at: datetime
    expires_at: datetime


# --- Lecturas del gestor (SPEC-W-010 hito 2) -------------------------------------------------------------------------------------------


class PortfolioEntry(BaseModel):
    """Un autónomo de la cartera del gestor, con sus pendientes (documentos para revisar)."""

    id: UUID = Field(
        description="Identificador del autónomo (la `owner_id` de las rutas `/api/gestor/autonomos/{owner_id}`)"
    )
    name: str
    email: str
    pending_count: int = Field(ge=0, description="Documentos en estado `review`; 0 si no tiene pendientes")


class SignedUrl(BaseModel):
    """Una descarga por URL firmada de corta vida (ADR-0016: los archivos no pasan por la API)."""

    url: str
    expires_in: int


class ProfileView(BaseModel):
    """El perfil del negocio de un autónomo (IBAN incluido, P-01) y sus series de facturación."""

    profile: Profile
    series: list[InvoiceSeries]


class ExpenseListPage(BaseModel):
    """Una página de gastos del autónomo, con los anulados (`voided_at`) a la vista."""

    items: list[Expense]
    next_cursor: str | None


class NoteInput(BaseModel):
    body: str = Field(max_length=4000, description="Texto de la anotación (1 a 2.000 caracteres tras recortar)")
    entity_type: Literal["invoice", "expense", "document"] | None = None
    entity_id: UUID | None = None


class GestorNote(BaseModel):
    id: UUID
    body: str
    entity_type: Literal["invoice", "expense", "document"] | None
    entity_id: UUID | None
    created_at: datetime
    gestor_email: str | None = Field(description="Correo del gestor que la escribió (solo lo ve el autónomo)")


class ActivityEntry(BaseModel):
    """Una entrada del registro de actividad de acceso de un autónomo. Sin datos financieros: solo qué, quién y cuándo."""

    id: int
    occurred_at: datetime
    action: str = Field(
        description="`gestor_access.invited|accepted|declined|revoked`, `gestor.read` o `gestor.note_added`"
    )
    actor_role: Literal["usuario", "gestor", "admin"] | None
    actor_email: str | None = Field(description="Correo del gestor que actuó; vacío si actuó el propio autónomo")
    entity_type: str | None
    entity_id: str | None
    year: int | None = Field(description="Año del borrador consultado (solo en lecturas del 303 y del 130)")
    quarter: int | None


class ActivityPage(BaseModel):
    items: list[ActivityEntry]
    next_cursor: str | None


class AutonomoSummary(PortfolioEntry):
    """La ficha de un autónomo de la cartera: lo mismo que su fila de la cartera (nombre, correo y pendientes)."""
