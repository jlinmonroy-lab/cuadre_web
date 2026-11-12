"""Modelos de la API del acceso del gestor (SPEC-W-010 §5.1 y §5.3). De ellos sale el cliente TypeScript."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

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
