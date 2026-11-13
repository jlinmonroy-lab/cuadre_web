"""Modelos de la API de los ajustes de recordatorios (SPEC-W-014 §5.3). De ellos sale el cliente TypeScript.

La entrada es estricta en el TIPO (un booleano y un entero de verdad, no `"7"` ni `true` como número) pero NO en el rango: el rango de la antelación
lo decide el servicio, para devolver el código estable `invalid_lead_days` y no el error genérico de validación.
"""

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt


class ReminderSettings(BaseModel):
    enabled: bool = Field(description="`true` si la persona recibe un correo antes de cada plazo trimestral")
    lead_days: int = Field(description="Días de antelación del aviso respecto al plazo del 303 y el 130 (1 a 30)")


class ReminderSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool
    lead_days: StrictInt = Field(description="De 1 a 30; fuera de ese rango responde `422 invalid_lead_days`")
