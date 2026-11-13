"""Ajustes de los recordatorios por correo de cada persona (SPEC-W-014 §5.3): activarlos y elegir la antelación."""

from cuadre.reminders.models import ReminderSettings, ReminderSettingsInput
from cuadre.reminders.service import ReminderSettingsService

__all__ = ["ReminderSettings", "ReminderSettingsInput", "ReminderSettingsService"]
