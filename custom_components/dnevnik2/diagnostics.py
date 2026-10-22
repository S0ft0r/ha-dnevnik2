"""Диагностика интеграции Электронный дневник СПб (ссылка «Скачать диагностику» в карточке устройства)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_FALLBACK_TOKEN, CONF_TOKEN, DOMAIN, SESSION_COOKIE
from .manager import Dnevnik2Coordinator

TO_REDACT = {
    CONF_TOKEN,
    CONF_FALLBACK_TOKEN,
    SESSION_COOKIE,
    "full_name",
    "short_name",
    "first_name",
    "person_id",
    "education_id",
    "hash_uid",
    "teacher",
}


def _serialize_state(
    hass: HomeAssistant, entity_id: str | None
) -> dict[str, Any] | None:
    """Сериализует текущее состояние и атрибуты сущности с маскированием персональных данных."""
    if not entity_id:
        return None
    st = hass.states.get(entity_id)
    if st is None:
        return {"entity_id": entity_id, "state": "missing"}
    return {
        "entity_id": entity_id,
        "name": st.name,
        "state": st.state,
        "attributes": async_redact_data(dict(st.attributes), TO_REDACT),
        "last_changed": st.last_changed.isoformat() if st.last_changed else None,
        "last_updated": st.last_updated.isoformat() if st.last_updated else None,
    }


def _build_common_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Dnevnik2Coordinator | None,
) -> dict[str, Any]:
    """Формирует общий обезличенный снимок состояния интеграции."""
    students_dump = (
        {
            f"student_{idx}": asdict(st)
            for idx, st in enumerate(coordinator.students.values(), start=1)
        }
        if coordinator
        else {}
    )
    raw: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "runtime": {
            "last_update_success": (
                coordinator.last_update_success if coordinator else None
            ),
            "homework_mode": coordinator.homework_mode if coordinator else None,
            "lessons_mode": coordinator.lessons_mode if coordinator else None,
            "scan_interval_minutes": (
                coordinator.scan_interval_minutes if coordinator else None
            ),
            "students_count": len(students_dump),
            "token_diagnostics": (
                coordinator.client.token_diagnostics if coordinator else None
            ),
        },
        "students": students_dump,
    }
    return async_redact_data(raw, TO_REDACT)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Возвращает диагностические данные для записи конфигурации (ConfigEntry)."""
    coordinator: Dnevnik2Coordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    return _build_common_diagnostics(hass, entry, coordinator)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Возвращает диагностические данные для карточки основного устройства или подустройства учащегося."""
    coordinator: Dnevnik2Coordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    diag = _build_common_diagnostics(hass, entry, coordinator)

    ent_reg = er.async_get(hass)
    device_entities = [
        _serialize_state(hass, ent_entry.entity_id)
        for ent_entry in er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        )
    ]

    diag["device"] = async_redact_data(
        {
            "model": device.model,
            "manufacturer": device.manufacturer,
            "area_id": device.area_id,
            "entities": device_entities,
        },
        TO_REDACT,
    )
    return diag
