"""Интеграция Электронный дневник СПб (dnevnik2.petersburgedu.ru)."""

from __future__ import annotations

from datetime import timedelta
import hashlib
import hmac
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

from aiohttp import web

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.lovelace import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    BASE_URL,
    DOMAIN,
    EP_FILEKIT_DOWNLOAD,
    FILE_PROXY_URL_PATH,
    KEEP_ALIVE_INTERVAL_MIN,
    OUTPUT_MODE_SENSOR,
    OUTPUT_MODE_TODO,
)
from .manager import Dnevnik2Coordinator

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.TODO,
    Platform.CALENDAR,
]


class Dnevnik2FileProxyView(HomeAssistantView):
    """HTTP-прокси скачивания прикреплённых к домашним заданиям файлов по активной сессии интеграции."""

    url = FILE_PROXY_URL_PATH
    name = f"api:{DOMAIN}:file"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Инициализация прокси-обработчика файлов."""
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, file_uuid: str
    ) -> web.StreamResponse:
        """Скачивает файл с портала по текущей сессии координатора и отдаёт клиенту."""
        coordinator: Dnevnik2Coordinator | None = self.hass.data.get(
            DOMAIN, {}
        ).get(entry_id)
        if not isinstance(coordinator, Dnevnik2Coordinator):
            return web.Response(status=404, text="Integration entry not found")

        sig = request.query.get("sig", "")
        expected_sig = coordinator.file_download_signature(file_uuid)
        if not sig or not hmac.compare_digest(sig, expected_sig):
            return web.Response(status=403, text="Invalid file signature")

        file_name = request.query.get("name", "") or f"{file_uuid}.bin"
        result = await coordinator.client.async_download_file(file_uuid)
        if result is None:
            direct_url = f"{BASE_URL}{EP_FILEKIT_DOWNLOAD}?p_uuid={file_uuid}"
            raise web.HTTPFound(location=direct_url)

        body, content_type, content_disp = result
        headers: dict[str, str] = {"Content-Type": content_type}
        if content_disp:
            headers["Content-Disposition"] = content_disp
        else:
            encoded_name = quote(file_name)
            headers["Content-Disposition"] = (
                f"attachment; filename*=UTF-8''{encoded_name}"
            )
        return web.Response(body=body, headers=headers)


async def _async_upsert_lovelace_resource(
    hass: HomeAssistant, url: str
) -> bool:
    """Регистрирует JS-модуль в storage-ресурсах Lovelace после запуска frontend."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if getattr(lovelace_data, "resource_mode", None) != MODE_STORAGE:
        return False

    resources = getattr(lovelace_data, "resources", None)
    if resources is None or not all(
        hasattr(resources, method)
        for method in (
            "async_get_info",
            "async_items",
            "async_create_item",
            "async_update_item",
            "async_delete_item",
        )
    ):
        return False

    # async_items() у storage-коллекции требует предварительной загрузки.
    await resources.async_get_info()
    base_url = url.split("?", 1)[0]
    matches = [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?", 1)[0] == base_url
    ]

    if not matches:
        await resources.async_create_item({"url": url, "res_type": "module"})
        return True

    primary = matches[0]
    updates: dict[str, str] = {}
    if primary.get("url") != url:
        updates["url"] = url
    if primary.get("type") != "module":
        updates["res_type"] = "module"
    if updates:
        await resources.async_update_item(primary["id"], updates)

    for duplicate in matches[1:]:
        await resources.async_delete_item(duplicate["id"])
    return True


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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed as err:
        _LOGGER.warning("%s: %s", entry.title, err)
        entry.async_start_reauth(hass)
    except ConfigEntryNotReady as err:
        if not coordinator.known_students:
            raise
        _LOGGER.warning("%s: %s", entry.title, err)

    frontend_dir = Path(__file__).parent / "frontend"
    js_assets = [
        (f"{DOMAIN}-icons.js", f"/{DOMAIN}_static/{DOMAIN}-icons.js"),
        (f"{DOMAIN}-card.js", f"/{DOMAIN}_static/{DOMAIN}-card.js"),
    ]
    if getattr(hass, "http", None) is not None:
        try:
            if not hass.data[DOMAIN].get("_file_proxy_registered"):
                hass.http.register_view(Dnevnik2FileProxyView(hass))
                hass.data[DOMAIN]["_file_proxy_registered"] = True

            existing_assets = [
                (frontend_dir / fname, url_path)
                for fname, url_path in js_assets
                if (frontend_dir / fname).is_file()
            ]
            if existing_assets and not hass.data[DOMAIN].get(
                "_frontend_registered"
            ):
                if hasattr(hass.http, "async_register_static_paths"):
                    await hass.http.async_register_static_paths(
                        [
                            StaticPathConfig(
                                url_path, str(fpath), cache_headers=False
                            )
                            for fpath, url_path in existing_assets
                        ]
                    )
                elif hasattr(hass.http, "register_static_path"):
                    for fpath, url_path in existing_assets:
                        hass.http.register_static_path(
                            url_path, str(fpath), cache_headers=False
                        )
                hass.data[DOMAIN]["_frontend_registered"] = True

            mtime_map: dict[str, int | str] = hass.data[DOMAIN].setdefault(
                "_frontend_mtimes", {}
            )
            resource_revision = hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest()[:8]
            lovelace_data = hass.data.get(LOVELACE_DATA)
            storage_resource_mode = (
                getattr(lovelace_data, "resource_mode", None) == MODE_STORAGE
            )
            for fpath, url_path in existing_assets:
                ver = f"{int(fpath.stat().st_mtime)}-{resource_revision}"
                module_url = f"{url_path}?v={ver}"
                previous_ver = mtime_map.get(url_path)

                if storage_resource_mode:
                    # Старый app-shell import мог зарегистрировать элемент до
                    # scoped custom element registry (HA 2026.9+). Убираем его
                    # и загружаем модуль только как обычный ресурс Lovelace.
                    if previous_ver is not None:
                        remove_extra_js_url(
                            hass, f"{url_path}?v={previous_ver}"
                        )
                    try:
                        resource_registered = (
                            await _async_upsert_lovelace_resource(hass, module_url)
                        )
                    except Exception as err:
                        _LOGGER.warning(
                            "Failed to register %s as a Lovelace resource: %s",
                            url_path,
                            err,
                        )
                        resource_registered = False
                    if not resource_registered:
                        _LOGGER.warning(
                            "Lovelace resource storage is unavailable; "
                            "falling back to the frontend module URL for %s",
                            url_path,
                        )
                        add_extra_js_url(hass, module_url)
                elif previous_ver != ver:
                    if previous_ver is not None:
                        remove_extra_js_url(
                            hass, f"{url_path}?v={previous_ver}"
                        )
                    add_extra_js_url(hass, module_url)

                mtime_map[url_path] = ver
        except Exception as err:
            _LOGGER.warning(
                "Failed to register %s frontend assets: %s", DOMAIN, err
            )

    dev_reg = dr.async_get(hass)
    main_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        **coordinator.device_info,
    )
    coordinator.main_device_id = main_device.id

    for edu_id, student in coordinator.known_students.items():
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

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            coordinator.async_keep_alive_tick,
            timedelta(minutes=KEEP_ALIVE_INTERVAL_MIN),
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Перезагрузка при изменении настроек (пропуская фоновое автообновление токена и лимита баланса)."""
    coordinator: Dnevnik2Coordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator and not coordinator.should_reload_on_entry_update(entry):
        coordinator.async_update_listeners()
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
    enable_cal = coordinator.enable_calendar

    for ent in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        uid = ent.unique_id or ""
        if uid.endswith("_meal_balance"):
            ent_reg.async_remove(ent.entity_id)
            continue
        if ent.domain == "calendar" and not enable_cal:
            ent_reg.async_remove(ent.entity_id)
            continue
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
    if not coordinator.last_update_success:
        return
    active_identifiers = {(DOMAIN, entry.entry_id)} | {
        (DOMAIN, f"{entry.entry_id}_student_{edu_id}")
        for edu_id in coordinator.known_students
    }
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if not device.identifiers & active_identifiers:
            dev_reg.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Разрешить удаление подустройств учеников, но не основного устройства."""
    return (DOMAIN, entry.entry_id) not in device.identifiers
