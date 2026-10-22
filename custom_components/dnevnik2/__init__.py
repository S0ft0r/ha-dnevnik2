"""Интеграция Электронный дневник СПб (dnevnik2.petersburgedu.ru)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import DOMAIN, OUTPUT_MODE_SENSOR, OUTPUT_MODE_TODO
from .manager import Dnevnik2Coordinator

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.TODO,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Загрузка интеграции, регистрация кастомных иконок и подустройств учеников."""
    cache = hass.data.get("translation_flatten_cache")
    if cache is not None:
        loaded = getattr(cache, "loaded", None)
        if isinstance(loaded, dict):
            for comp_set in loaded.values():
                if isinstance(comp_set, set):
                    comp_set.discard(DOMAIN)
        raw_cache = getattr(cache, "cache", None)
        if isinstance(raw_cache, dict):
            for lang_cache in raw_cache.values():
                if isinstance(lang_cache, dict):
                    for category_cache in lang_cache.values():
                        if isinstance(category_cache, dict):
                            category_cache.pop(DOMAIN, None)

    coordinator = Dnevnik2Coordinator(hass, entry)
    await coordinator.async_init_translations()
    _LOGGER.info("%s", coordinator.tr_log("log_setup_entry", title=entry.title))

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    if not hass.data[DOMAIN].get("_frontend_registered"):
        js_file = Path(__file__).parent / "frontend" / f"{DOMAIN}-icons.js"
        if js_file.is_file() and getattr(hass, "http", None) is not None:
            url_path = f"/{DOMAIN}_static/{DOMAIN}-icons.js"
            try:
                if hasattr(hass.http, "async_register_static_paths"):
                    await hass.http.async_register_static_paths(
                        [StaticPathConfig(url_path, str(js_file), cache_headers=False)]
                    )
                elif hasattr(hass.http, "register_static_path"):
                    hass.http.register_static_path(
                        url_path, str(js_file), cache_headers=False
                    )
                ver = int(js_file.stat().st_mtime)
                add_extra_js_url(hass, f"{url_path}?v={ver}")
                hass.data[DOMAIN]["_frontend_registered"] = True
            except Exception as err:
                _LOGGER.warning("Failed to register %s custom icons: %s", DOMAIN, err)

    dev_reg = dr.async_get(hass)
    main_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinator.device_info,
    )
    coordinator.main_device_id = main_device.id

    for edu_id, student in coordinator.students.items():
        dev_info = coordinator.device_info_for_student(student)
        sub_device = dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            **dev_info,
        )
        expected_name = dev_info.get("name")
        expected_model = dev_info.get("model")
        update_kwargs: dict[str, Any] = {}
        if expected_name and sub_device.name != expected_name:
            update_kwargs["name"] = expected_name
        if expected_model and sub_device.model != expected_model:
            update_kwargs["model"] = expected_model
        if update_kwargs:
            sub_device = (
                dev_reg.async_update_device(sub_device.id, **update_kwargs)
                or sub_device
            )
        if main_device.area_id and sub_device.area_id is None:
            sub_device = (
                dev_reg.async_update_device(
                    sub_device.id, area_id=main_device.area_id
                )
                or sub_device
            )
        coordinator.student_device_ids[edu_id] = sub_device.id

    @callback
    def _async_on_device_registry_updated(event) -> None:
        """Автоматически наследовать Пространство (area_id) основного устройства для подустройств учеников."""
        if event.data.get("action") != "update":
            return
        if event.data.get("device_id") != coordinator.main_device_id:
            return
        if "area_id" not in event.data.get("changes", {}):
            return
        updated_main = dev_reg.async_get(coordinator.main_device_id)
        if not updated_main or not updated_main.area_id:
            return
        for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if dev.id != coordinator.main_device_id and dev.area_id is None:
                dev_reg.async_update_device(dev.id, area_id=updated_main.area_id)

    entry.async_on_unload(
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _async_on_device_registry_updated
        )
    )

    _remove_stale_mode_entities(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_stale_devices(dev_reg, entry, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузка при изменении настроек (пропуская фоновое автообновление токена)."""
    coordinator: Dnevnik2Coordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator and coordinator.consume_ignore_options_update():
        return
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _remove_stale_mode_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: Dnevnik2Coordinator,
) -> None:
    """Удаляет неактивные сущности (sensor vs todo) при переключении режима вывода в настройках."""
    ent_reg = er.async_get(hass)
    hw_mode = coordinator.homework_mode
    lessons_mode = coordinator.lessons_mode

    for ent in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        uid = ent.unique_id or ""
        if uid.endswith("_homework") or uid.endswith("_homework_tomorrow"):
            if ent.domain == "sensor" and hw_mode != OUTPUT_MODE_SENSOR:
                ent_reg.async_remove(ent.entity_id)
                continue
            if ent.domain == "todo" and hw_mode != OUTPUT_MODE_TODO:
                ent_reg.async_remove(ent.entity_id)
                continue
        elif uid.endswith("_lessons_today"):
            if ent.domain == "sensor" and lessons_mode != OUTPUT_MODE_SENSOR:
                ent_reg.async_remove(ent.entity_id)
                continue
            if ent.domain == "todo" and lessons_mode != OUTPUT_MODE_TODO:
                ent_reg.async_remove(ent.entity_id)
                continue

        if ent.domain == "todo":
            if uid.endswith("_homework"):
                ent_reg.async_update_entity(
                    ent.entity_id,
                    has_entity_name=True,
                    original_name=coordinator.tr_entity_name(
                        "todo", "homework"
                    ),
                )
            elif uid.endswith("_lessons_today"):
                ent_reg.async_update_entity(
                    ent.entity_id,
                    has_entity_name=True,
                    original_name=coordinator.tr_entity_name(
                        "todo", "lessons_today"
                    ),
                )


@callback
def _remove_stale_devices(
    dev_reg: dr.DeviceRegistry,
    entry: ConfigEntry,
    coordinator: Dnevnik2Coordinator,
) -> None:
    """Удаляет подустройства учеников, которых больше нет в аккаунте."""
    active_identifiers = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, f"{entry.entry_id}_student_{edu_id}")
        for edu_id in coordinator.students
    }
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not device.identifiers & active_identifiers:
            dev_reg.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Разрешить удаление подустройств учеников, но не основного устройства."""
    return (DOMAIN, entry.entry_id) not in device.identifiers
