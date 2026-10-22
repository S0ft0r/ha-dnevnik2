"""Мастер первоначальной настройки (ConfigFlow) и параметров (OptionsFlow) Электронного дневника СПб."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, DummyCookieJar
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, selector

from . import client as _client_mod, const as _const_mod

if not hasattr(_const_mod, "CONF_TOKEN") or not hasattr(_const_mod, "LOGIN_PAGE_URL"):
    try:
        _const_mod = importlib.reload(_const_mod)
    except Exception:
        pass

if not hasattr(_client_mod, "extract_jwt_token") or not hasattr(
    _client_mod.Dnevnik2Client, "async_validate_and_fetch_students"
):
    try:
        _client_mod = importlib.reload(_client_mod)
    except Exception:
        pass

Dnevnik2AuthError = _client_mod.Dnevnik2AuthError
Dnevnik2Client = _client_mod.Dnevnik2Client
Dnevnik2ConnectionError = _client_mod.Dnevnik2ConnectionError
clear_petersburgedu_cookies = getattr(
    _client_mod, "clear_petersburgedu_cookies", None
)
extract_jwt_token = getattr(_client_mod, "extract_jwt_token", None)

CONF_BALANCE_LIMIT = getattr(
    _const_mod, "CONF_BALANCE_LIMIT", "balance_limit"
)
CONF_FALLBACK_TOKEN = getattr(
    _const_mod, "CONF_FALLBACK_TOKEN", "fallback_token"
)
CONF_HOMEWORK_MODE = getattr(_const_mod, "CONF_HOMEWORK_MODE", "homework_mode")
CONF_LESSONS_MODE = getattr(_const_mod, "CONF_LESSONS_MODE", "lessons_mode")
CONF_NAME = getattr(_const_mod, "CONF_NAME", "name")
CONF_SCAN_INTERVAL = getattr(_const_mod, "CONF_SCAN_INTERVAL", "scan_interval")
CONF_TOKEN = getattr(_const_mod, "CONF_TOKEN", "token")
DEFAULT_BALANCE_LIMIT = getattr(_const_mod, "DEFAULT_BALANCE_LIMIT", 200)
DEFAULT_HOMEWORK_MODE = getattr(_const_mod, "DEFAULT_HOMEWORK_MODE", "todo")
DEFAULT_LESSONS_MODE = getattr(_const_mod, "DEFAULT_LESSONS_MODE", "todo")
DEFAULT_SCAN_INTERVAL_MIN = getattr(_const_mod, "DEFAULT_SCAN_INTERVAL_MIN", 30)
DOMAIN = getattr(_const_mod, "DOMAIN", "dnevnik2")
LOGIN_PAGE_URL = getattr(
    _const_mod, "LOGIN_PAGE_URL", "https://dnevnik2.petersburgedu.ru/login"
)
MAX_BALANCE_LIMIT = getattr(_const_mod, "MAX_BALANCE_LIMIT", 5000)
MAX_SCAN_INTERVAL_MIN = getattr(_const_mod, "MAX_SCAN_INTERVAL_MIN", 180)
MIN_BALANCE_LIMIT = getattr(_const_mod, "MIN_BALANCE_LIMIT", 0)
MIN_SCAN_INTERVAL_MIN = getattr(_const_mod, "MIN_SCAN_INTERVAL_MIN", 10)
OUTPUT_MODES = getattr(_const_mod, "OUTPUT_MODES", ("todo", "sensor"))
STEP_BALANCE_LIMIT = getattr(_const_mod, "STEP_BALANCE_LIMIT", 50)

_TRANSLATIONS_FILE = Path(__file__).parent / "translations" / "ru.json"


def _invalidate_ha_translation_cache(hass: HomeAssistant) -> None:
    """Сбрасывает внутренний кэш переводов Home Assistant для домена интеграции без перезапуска HA."""
    cache = hass.data.get("translation_flatten_cache")
    if cache is None:
        return
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


def _read_translation_data() -> tuple[str, dict[str, str]]:
    """Синхронно читает заголовок и шаблоны common из файла локализации."""
    try:
        data = json.loads(_TRANSLATIONS_FILE.read_text(encoding="utf-8"))
        title = str(data.get("title") or DOMAIN)
        common = {str(k): str(v) for k, v in (data.get("common") or {}).items()}
        return title, common
    except Exception:
        return DOMAIN, {}


async def _async_load_translation_data(
    hass: HomeAssistant,
) -> tuple[str, dict[str, str]]:
    """Асинхронно загружает заголовок и шаблоны common из translations/ru.json."""
    return await hass.async_add_executor_job(_read_translation_data)


def _is_mobile_or_companion_request() -> bool:
    """Определяет по HTTP-заголовку User-Agent, открыт ли мастер с телефона или HA Companion."""
    try:
        from homeassistant.components.http import current_request as comp_req

        req = comp_req.get()
    except Exception:
        try:
            from homeassistant.helpers.http import current_request as helper_req

            req = helper_req.get()
        except Exception:
            req = None
    if req is None:
        return False
    ua = (req.headers.get("User-Agent") or "").lower()
    mobile_markers = (
        "homeassistant",
        "home assistant",
        "android",
        "iphone",
        "ipad",
        "mobile",
    )
    return any(marker in ua for marker in mobile_markers)


def _get_isolated_session(hass: HomeAssistant) -> ClientSession:
    """Возвращает сессию aiohttp с DummyCookieJar и очищает общий CookieJar HA от старых cookie."""
    shared = aiohttp_client.async_get_clientsession(hass, verify_ssl=False)
    if callable(clear_petersburgedu_cookies):
        clear_petersburgedu_cookies(shared)
    return aiohttp_client.async_create_clientsession(
        hass,
        verify_ssl=False,
        cookie_jar=DummyCookieJar(),
    )


async def _async_get_esia_url(hass: HomeAssistant) -> str:
    """Запрашивает актуальную ссылку авторизации через Госуслуги (ЕСИА)."""
    session = _get_isolated_session(hass)
    client = Dnevnik2Client(session)
    if hasattr(client, "async_get_esia_login_url"):
        return await client.async_get_esia_login_url()
    return LOGIN_PAGE_URL


async def _async_validate_students(
    client: Dnevnik2Client,
) -> list[dict[str, Any]]:
    """Проверяет токен и возвращает список учеников через async_validate_and_fetch_students или async_get_children."""
    if hasattr(client, "async_validate_and_fetch_students"):
        return await client.async_validate_and_fetch_students()
    children_raw = await client.async_get_children()
    students: list[dict[str, Any]] = []
    for child in children_raw:
        firstname = str(
            child.get("firstname")
            or child.get("first_name")
            or child.get("name")
            or ""
        ).strip()
        educations = child.get("educations")
        if isinstance(educations, list) and educations:
            for edu in educations:
                if not isinstance(edu, dict):
                    continue
                edu_id = str(
                    edu.get("education_id") or edu.get("id") or ""
                ).strip()
                if not edu_id:
                    continue
                group_name = str(
                    edu.get("group_name") or edu.get("class_name") or ""
                ).strip()
                students.append(
                    {
                        "education_id": edu_id,
                        "first_name": firstname or edu_id,
                        "full_name": firstname or edu_id,
                        "group_name": group_name,
                    }
                )
        else:
            edu_id = str(
                child.get("education_id") or child.get("id") or ""
            ).strip()
            if edu_id:
                students.append(
                    {
                        "education_id": edu_id,
                        "first_name": firstname or edu_id,
                        "full_name": firstname or edu_id,
                        "group_name": str(child.get("group_name") or "").strip(),
                    }
                )
    return students


class Dnevnik2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Двухшаговый мастер подключения к Электронному дневнику СПб."""

    VERSION = 1

    def __init__(self) -> None:
        """Инициализация состояния мастера."""
        self._reauth_entry: ConfigEntry | None = None
        self._validated_token: str | None = None
        self._students_summary: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Шаг 1: пошаговая инструкция и ввод только токена X-JWT-Token."""
        _invalidate_ha_translation_cache(self.hass)
        errors: dict[str, str] = {}
        _, common = await _async_load_translation_data(self.hass)

        if user_input is not None:
            raw_token = str(user_input.get(CONF_TOKEN) or "").strip()
            token = (
                extract_jwt_token(raw_token)
                if callable(extract_jwt_token)
                else raw_token
            )
            if not token:
                errors["base"] = "invalid_token_format"
            else:
                session = _get_isolated_session(self.hass)
                client = Dnevnik2Client(session, token=token)
                try:
                    students = await _async_validate_students(client)
                except Dnevnik2AuthError:
                    errors["base"] = "invalid_auth"
                except Dnevnik2ConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    if not students:
                        errors["base"] = "no_students_found"
                    else:
                        edu_ids = "_".join(
                            sorted(str(s["education_id"]) for s in students)
                        )
                        await self.async_set_unique_id(f"{DOMAIN}_{edu_ids}")
                        self._abort_if_unique_id_configured()

                        self._validated_token = client.token or token
                        item_tpl = common.get(
                            "student_with_group", "{name} ({group})"
                        )
                        parts: list[str] = []
                        for st in students:
                            fname = str(
                                st.get("first_name") or st.get("full_name") or ""
                            )
                            grp = " ".join(str(st.get("group_name") or "").split())
                            grp = "".join(
                                grp.split()
                                if len(grp.split()) == 2 and grp.split()[0].isdigit()
                                else [grp]
                            )
                            if grp:
                                parts.append(item_tpl.format(name=fname, group=grp))
                            else:
                                parts.append(fname)
                        self._students_summary = ", ".join(parts)
                        return await self.async_step_settings()

        esia_url = await _async_get_esia_url(self.hass)
        client_hint = ""
        if _is_mobile_or_companion_request():
            hint_text = common.get("client_hint_companion", "")
            if hint_text:
                client_hint = f"\n\n{hint_text}"

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "esia_url": esia_url or LOGIN_PAGE_URL,
                "client_hint": client_hint,
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Шаг 2: выбор названия интеграции, формата вывода ДЗ/уроков и интервала опроса."""
        if not self._validated_token:
            return await self.async_step_user()

        default_title, _ = await _async_load_translation_data(self.hass)

        if user_input is not None:
            title = str(user_input.get(CONF_NAME) or default_title).strip()
            homework_mode = str(
                user_input.get(CONF_HOMEWORK_MODE, DEFAULT_HOMEWORK_MODE)
            )
            lessons_mode = str(
                user_input.get(CONF_LESSONS_MODE, DEFAULT_LESSONS_MODE)
            )
            scan_interval = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
            )
            balance_limit = int(
                user_input.get(CONF_BALANCE_LIMIT, DEFAULT_BALANCE_LIMIT)
            )
            return self.async_create_entry(
                title=title,
                data={
                    CONF_NAME: title,
                    CONF_TOKEN: self._validated_token,
                    CONF_FALLBACK_TOKEN: self._validated_token,
                    CONF_HOMEWORK_MODE: homework_mode,
                    CONF_LESSONS_MODE: lessons_mode,
                    CONF_SCAN_INTERVAL: scan_interval,
                    CONF_BALANCE_LIMIT: balance_limit,
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=default_title): selector.TextSelector(),
                vol.Required(
                    CONF_HOMEWORK_MODE, default=DEFAULT_HOMEWORK_MODE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(OUTPUT_MODES),
                        translation_key="output_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_LESSONS_MODE, default=DEFAULT_LESSONS_MODE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(OUTPUT_MODES),
                        translation_key="output_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_BALANCE_LIMIT, default=DEFAULT_BALANCE_LIMIT
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_BALANCE_LIMIT,
                        max=MAX_BALANCE_LIMIT,
                        step=STEP_BALANCE_LIMIT,
                        unit_of_measurement="RUB",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MIN
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MIN,
                        max=MAX_SCAN_INTERVAL_MIN,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="settings",
            data_schema=schema,
            description_placeholders={
                "students_summary": self._students_summary,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Запуск повторной авторизации при истечении X-JWT-Token."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Подтверждение нового токена при повторной авторизации."""
        _invalidate_ha_translation_cache(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None and self._reauth_entry is not None:
            raw_token = str(user_input.get(CONF_TOKEN) or "").strip()
            token = (
                extract_jwt_token(raw_token)
                if callable(extract_jwt_token)
                else raw_token
            )
            if not token:
                errors["base"] = "invalid_token_format"
            else:
                session = _get_isolated_session(self.hass)
                client = Dnevnik2Client(session, token=token)
                try:
                    await _async_validate_students(client)
                except Dnevnik2AuthError:
                    errors["base"] = "invalid_auth"
                except Dnevnik2ConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    new_data = {
                        **self._reauth_entry.data,
                        CONF_TOKEN: client.token or token,
                        CONF_FALLBACK_TOKEN: token,
                    }
                    self.hass.config_entries.async_update_entry(
                        self._reauth_entry, data=new_data
                    )
                    await self.hass.config_entries.async_reload(
                        self._reauth_entry.entry_id
                    )
                    return self.async_abort(reason="reauth_successful")

        esia_url = await _async_get_esia_url(self.hass)
        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "esia_url": esia_url or LOGIN_PAGE_URL,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Возвращает обработчик настроек интеграции."""
        return Dnevnik2OptionsFlow(config_entry)


class Dnevnik2OptionsFlow(OptionsFlow):
    """Настройка параметров опроса, обновления токена и формата вывода ДЗ/уроков."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Сохранение ссылки на ConfigEntry."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Единое окно настроек интеграции."""
        _invalidate_ha_translation_cache(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            new_options = dict(self._entry.options)
            new_options[CONF_HOMEWORK_MODE] = str(
                user_input.get(CONF_HOMEWORK_MODE, DEFAULT_HOMEWORK_MODE)
            )
            new_options[CONF_LESSONS_MODE] = str(
                user_input.get(CONF_LESSONS_MODE, DEFAULT_LESSONS_MODE)
            )
            new_options[CONF_SCAN_INTERVAL] = int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)
            )

            raw_token = str(user_input.get(CONF_TOKEN) or "").strip()
            if raw_token:
                token = (
                    extract_jwt_token(raw_token)
                    if callable(extract_jwt_token)
                    else raw_token
                )
                if not token:
                    errors["base"] = "invalid_token_format"
                else:
                    session = _get_isolated_session(self.hass)
                    client = Dnevnik2Client(session, token=token)
                    try:
                        await _async_validate_students(client)
                    except Dnevnik2AuthError:
                        errors["base"] = "invalid_auth"
                    except Dnevnik2ConnectionError:
                        errors["base"] = "cannot_connect"
                    except Exception:
                        errors["base"] = "cannot_connect"
                    else:
                        new_data = {
                            **self._entry.data,
                            CONF_TOKEN: client.token or token,
                            CONF_FALLBACK_TOKEN: token,
                        }
                        self.hass.config_entries.async_update_entry(
                            self._entry, data=new_data
                        )

            if not errors:
                return self.async_create_entry(title="", data=new_options)

        current_hw_mode = self._entry.options.get(
            CONF_HOMEWORK_MODE,
            self._entry.data.get(CONF_HOMEWORK_MODE, DEFAULT_HOMEWORK_MODE),
        )
        current_ls_mode = self._entry.options.get(
            CONF_LESSONS_MODE,
            self._entry.data.get(CONF_LESSONS_MODE, DEFAULT_LESSONS_MODE),
        )
        current_interval = self._entry.options.get(
            CONF_SCAN_INTERVAL,
            self._entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOMEWORK_MODE, default=current_hw_mode
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(OUTPUT_MODES),
                        translation_key="output_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_LESSONS_MODE, default=current_ls_mode
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(OUTPUT_MODES),
                        translation_key="output_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MIN,
                        max=MAX_SCAN_INTERVAL_MIN,
                        step=5,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(CONF_TOKEN, default=""): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        multiline=False,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
