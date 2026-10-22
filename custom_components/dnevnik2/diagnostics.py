"""Диагностическая выгрузка интеграции с маскированием токенов и персональных данных."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, DOMAIN, SESSION_COOKIE
from .manager import Dnevnik2Coordinator

TO_REDACT = {
    CONF_TOKEN,
    SESSION_COOKIE,
    "full_name",
    "short_name",
    "person_id",
    "education_id",
    "teacher",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Возвращает обезличенный диагностический снимок состояния интеграции."""
    coordinator: Dnevnik2Coordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    students_dump = (
        {
            edu_id: asdict(st)
            for edu_id, st in coordinator.students.items()
        }
        if coordinator
        else {}
    )
    raw = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "students_count": len(students_dump),
        "students": students_dump,
    }
    return async_redact_data(raw, TO_REDACT)
