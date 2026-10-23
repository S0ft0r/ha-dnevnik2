"""Координатор обновления данных и управления подустройствами учеников."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import hashlib
import hmac
import json
import logging
from pathlib import Path
import socket
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from aiohttp import DummyCookieJar

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import (
    async_create_clientsession,
    async_get_clientsession,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    Dnevnik2AuthError,
    Dnevnik2Client,
    Dnevnik2ConnectionError,
    clear_petersburgedu_cookies,
    normalize_group_name,
    unwrap_scalar,
)
from .const import (
    ABSENCE_CODE,
    BASE_URL,
    CONF_BALANCE_LIMIT,
    CONF_ENABLE_CALENDAR,
    CONF_FALLBACK_TOKEN,
    CONF_HOMEWORK_MODE,
    CONF_LESSONS_MODE,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    DEFAULT_BALANCE_LIMIT,
    DEFAULT_ENABLE_CALENDAR,
    DEFAULT_HOMEWORK_MODE,
    DEFAULT_LESSONS_MODE,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    EP_FILEKIT_DOWNLOAD,
    EVENT_LOW_BALANCE,
    EVENT_NEW_GRADE,
    EVENT_TURNSTILE,
    LATE_CODE,
    MAX_BALANCE_LIMIT,
    MIN_BALANCE_LIMIT,
)

_LOGGER = logging.getLogger(__name__)
SPB_TZ = ZoneInfo("Europe/Moscow")
STORAGE_VERSION = 1

_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y")
_DATETIME_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M",
)


def make_item_uid(
    prefix: str, education_id: str, due_date: date, title: str, detail: str
) -> str:
    """Формирует стабильный UID элемента (ДЗ или урока) для сохранения галочки в Todo."""
    raw = f"{prefix}:{education_id}:{due_date.isoformat()}:{title.strip()}:{detail.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _parse_lesson_date(raw_date: str) -> date | None:
    """Преобразует строку даты из API ('DD.MM.YYYY...' или 'YYYY-MM-DD...') в datetime.date."""
    val = raw_date.strip().split(" ")[0].split("T")[0]
    if not val:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(raw_dt: str) -> datetime | None:
    """Преобразует строку даты и времени из API в datetime."""
    candidate = raw_dt.strip().replace("T", " ")
    if not candidate:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(candidate, fmt)
        except ValueError:
            continue
    return None


def _extract_hhmm(raw_time: str) -> str:
    """Извлекает время 'HH:MM' из строки времени или полного datetime."""
    candidate = raw_time.strip().replace("T", " ")
    if not candidate:
        return ""
    if " " in candidate:
        candidate = candidate.split(" ")[-1]
    parts = candidate.split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    return candidate


@dataclass
class HomeworkFile:
    """Прикреплённый учителем файл к домашнему заданию."""

    name: str
    uuid: str
    url: str
    proxy_url: str


@dataclass
class HomeworkTask:
    """Одно домашнее задание ученика."""

    uid: str
    subject: str
    task: str
    due: date
    date_str: str
    files: list[HomeworkFile] = field(default_factory=list)


@dataclass
class LessonTask:
    """Один урок расписания ученика."""

    uid: str
    number: str
    subject: str
    time_from: str
    time_to: str
    room: str
    teacher: str
    due: date
    date_str: str
    homework_text: str = ""


@dataclass
class StudentData:
    """Агрегированные данные одного ученика (одного подустройства)."""

    education_id: str
    person_id: str
    full_name: str
    short_name: str
    first_name: str
    institution_name: str
    group_name: str
    group_id: str | None = None
    hash_uid: str = ""
    period_name: str = ""
    period_start_str: str = ""
    period_end_str: str = ""
    period_days_left: int | None = None
    periods_list: list[dict[str, Any]] = field(default_factory=list)
    average_grade: float | None = None
    grades_count: int = 0
    absences_count: int = 0
    lates_count: int = 0
    subject_averages: dict[str, float] = field(default_factory=dict)
    final_grades: dict[str, Any] = field(default_factory=dict)
    last_grade: str | None = None
    last_grade_attributes: dict[str, Any] = field(default_factory=dict)
    homework_tasks: list[HomeworkTask] = field(default_factory=list)
    homework_count: int = 0
    homework_attributes: dict[str, Any] = field(default_factory=dict)
    lesson_tasks: list[LessonTask] = field(default_factory=list)
    calendar_lessons: list[LessonTask] = field(default_factory=list)
    calendar_window_start: date | None = None
    calendar_window_end: date | None = None
    lessons_today_count: int = 0
    schedule_today_attributes: dict[str, Any] = field(default_factory=dict)
    at_school: bool | None = None
    last_turnstile_event: str | None = None
    turnstile_attributes: dict[str, Any] = field(default_factory=dict)
    meal_balance: float | None = None
    meal_hot_balance: float | None = None
    meal_buffet_balance: float | None = None
    meal_attributes: dict[str, Any] = field(default_factory=dict)
    meal_hot_attributes: dict[str, Any] = field(default_factory=dict)
    meal_buffet_attributes: dict[str, Any] = field(default_factory=dict)


def _pick_str(source: dict[str, Any], *keys: str) -> str:
    """Возвращает первую непустую строку по набору возможных ключей ответа API."""
    for key in keys:
        if key not in source:
            continue
        val = unwrap_scalar(source.get(key))
        if isinstance(val, bool):
            continue
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, (int, float)):
            return str(val)
    return ""


def _build_full_name(item: dict[str, Any]) -> tuple[str, str, str]:
    """Собирает полное, краткое ('Фамилия И.') и собственное ('Имя') имя ученика из карточки API."""
    surname = _pick_str(item, "surname", "last_name", "lastname")
    firstname = _pick_str(item, "firstname", "first_name", "name")
    middlename = _pick_str(item, "middlename", "middle_name", "patronymic")
    if surname or firstname:
        parts = [p for p in (surname, firstname, middlename) if p]
        full = " ".join(parts)
        short = f"{surname} {firstname[0]}." if surname and firstname else full
        first = firstname or surname or full
        return full, short, first

    fio = _pick_str(item, "child_fio", "fio", "full_name", "fullname")
    if fio:
        tokens = fio.split()
        short = f"{tokens[0]} {tokens[1][0]}." if len(tokens) >= 2 else fio
        first = tokens[1] if len(tokens) >= 2 else tokens[0]
        return fio, short, first

    edu_id = _pick_str(item, "education_id", "id") or "1"
    return f"#{edu_id}", f"#{edu_id}", f"#{edu_id}"


class Dnevnik2Coordinator(DataUpdateCoordinator[dict[str, StudentData]]):
    """Координатор опроса Электронного дневника СПб с подустройством на каждого ученика."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Инициализация координатора."""
        self.hass = hass
        self.entry = entry
        self.main_device_id: str | None = None
        self.student_device_ids: dict[str, str] = {}
        self._translations: dict[str, Any] = {}
        self._todo_store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}_todo_{entry.entry_id}"
        )
        self._completed_uids: set[str] = set()
        self._cached_students: dict[str, StudentData] = {}
        self._previous_students: dict[str, StudentData] | None = None
        self._known_grade_uids: dict[str, set[str]] = {}
        self._detected_today_grades: dict[tuple[str, date], list[dict[str, Any]]] = {}
        self._low_balance_alerted: dict[tuple[str, str], float] = {}
        self._group_periods_cache: dict[
            str, tuple[date, list[dict[str, Any]]]
        ] = {}
        self._consecutive_auth_failures: int = 0

        scan_minutes = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
            )
        )
        token = str(entry.data.get(CONF_TOKEN, ""))
        fallback_token = str(entry.data.get(CONF_FALLBACK_TOKEN, "") or token)
        session = self._make_http_session()
        self.client = Dnevnik2Client(
            session=session,
            token=token,
            fallback_token=fallback_token,
            on_token_refreshed=self._on_token_refreshed,
            on_diag_updated=self._on_diag_updated,
        )
        self._loaded_signature = self.config_signature

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=scan_minutes),
        )

    @callback
    def _make_http_session(self):
        """Создаёт чистую изолированную IPv4 HTTP-сессию без кэширования чужих cookie."""
        clear_petersburgedu_cookies(
            async_get_clientsession(self.hass, verify_ssl=False)
        )
        return async_create_clientsession(
            self.hass,
            verify_ssl=False,
            family=socket.AF_INET,
            cookie_jar=DummyCookieJar(),
        )

    @property
    def homework_mode(self) -> str:
        """Выбранный режим вывода домашних заданий ('todo' или 'sensor')."""
        return str(
            self.entry.options.get(
                CONF_HOMEWORK_MODE,
                self.entry.data.get(CONF_HOMEWORK_MODE, DEFAULT_HOMEWORK_MODE),
            )
        )

    @property
    def lessons_mode(self) -> str:
        """Выбранный режим вывода расписания уроков ('sensor' или 'todo')."""
        return str(
            self.entry.options.get(
                CONF_LESSONS_MODE,
                self.entry.data.get(CONF_LESSONS_MODE, DEFAULT_LESSONS_MODE),
            )
        )

    @property
    def enable_calendar(self) -> bool:
        """Включено ли создание сущностей календаря уроков (Platform.CALENDAR)."""
        return bool(
            self.entry.options.get(
                CONF_ENABLE_CALENDAR,
                self.entry.data.get(
                    CONF_ENABLE_CALENDAR, DEFAULT_ENABLE_CALENDAR
                ),
            )
        )

    @property
    def scan_interval_minutes(self) -> int:
        """Выбранный интервал полного обновления данных (мин.)."""
        return int(
            self.entry.options.get(
                CONF_SCAN_INTERVAL,
                self.entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
            )
        )

    @property
    def balance_limit(self) -> int:
        """Настроенный порог низкого баланса питания (Столовая / Буфет) в рублях."""
        return int(
            self.entry.options.get(
                CONF_BALANCE_LIMIT,
                self.entry.data.get(CONF_BALANCE_LIMIT, DEFAULT_BALANCE_LIMIT),
            )
        )

    async def async_set_balance_limit(self, new_limit: int) -> None:
        """Обновляет порог низкого баланса питания с основного устройства без перезагрузки."""
        clamped = max(MIN_BALANCE_LIMIT, min(MAX_BALANCE_LIMIT, int(new_limit)))
        self._low_balance_alerted.clear()
        new_options = {**self.entry.options, CONF_BALANCE_LIMIT: clamped}
        self.hass.config_entries.async_update_entry(
            self.entry, options=new_options
        )
        if self.data:
            self._emit_low_balance_events(None, self.data)
        self.async_update_listeners()

    @property
    def config_signature(self) -> tuple[str, str, bool, int]:
        """Сигнатура пользовательских настроек для фильтрации фонового обновления токена."""
        return (
            self.homework_mode,
            self.lessons_mode,
            self.enable_calendar,
            self.scan_interval_minutes,
        )

    def should_reload_on_entry_update(self, entry: ConfigEntry) -> bool:
        """Возвращает True только если изменились настройки или токен был заменён вручную."""
        new_token = str(entry.data.get(CONF_TOKEN, ""))
        if new_token and new_token not in (
            self.client.token,
            self.client.fallback_token,
        ):
            return True
        return self.config_signature != self._loaded_signature

    async def async_keep_alive_tick(self, _now: datetime | None = None) -> None:
        """Периодический фоновый пинг портала (раз в 4 мин.) для поддержания скользящей сессии."""
        ok = await self.client.async_keep_alive()
        if ok:
            self._consecutive_auth_failures = 0
            if not self.last_update_success:
                await self.async_request_refresh()
                return
        self.async_update_listeners()

    async def async_init_translations(self) -> None:
        """Асинхронно загружает локализацию и сохранённые отметки выполненных элементов Todo."""
        lang = (getattr(self.hass.config, "language", None) or "ru").lower()
        lang_code = "ru" if lang.startswith("ru") else "en"
        trans_dir = Path(__file__).parent / "translations"
        target_path = trans_dir / f"{lang_code}.json"
        fallback_path = trans_dir / "ru.json"

        def _load() -> dict[str, Any]:
            path = target_path if target_path.is_file() else fallback_path
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
            return {}

        self._translations = await self.hass.async_add_executor_job(_load)

        try:
            stored = await self._todo_store.async_load()
            if isinstance(stored, dict):
                completed = stored.get("completed_uids", [])
                if isinstance(completed, list):
                    self._completed_uids = {str(x) for x in completed if x}
                saved_diag = stored.get("token_diagnostics")
                if isinstance(saved_diag, dict):
                    self.client.restore_diagnostics(saved_diag)
                saved_students = stored.get("students_meta")
                if isinstance(saved_students, list):
                    for item in saved_students:
                        if not isinstance(item, dict):
                            continue
                        edu_id = str(item.get("education_id") or "").strip()
                        if not edu_id:
                            continue
                        self._cached_students[edu_id] = StudentData(
                            education_id=edu_id,
                            person_id=str(item.get("person_id") or edu_id),
                            full_name=str(item.get("full_name") or f"#{edu_id}"),
                            short_name=str(item.get("short_name") or f"#{edu_id}"),
                            first_name=str(item.get("first_name") or f"#{edu_id}"),
                            institution_name=str(
                                item.get("institution_name") or ""
                            ),
                            group_name=str(item.get("group_name") or ""),
                            group_id=item.get("group_id"),
                            hash_uid=str(item.get("hash_uid") or ""),
                        )
        except Exception as err:
            _LOGGER.debug("Todo store load skipped: %s", err)

    async def _async_persist_store(self) -> None:
        """Сохраняет выполненные пункты Todo, метаданные учеников и диагностику токена на диск."""
        try:
            active_students = self.data or self._cached_students
            students_meta = [
                {
                    "education_id": st.education_id,
                    "person_id": st.person_id,
                    "full_name": st.full_name,
                    "short_name": st.short_name,
                    "first_name": st.first_name,
                    "institution_name": st.institution_name,
                    "group_name": st.group_name,
                    "group_id": st.group_id,
                    "hash_uid": st.hash_uid,
                }
                for st in active_students.values()
            ]
            await self._todo_store.async_save(
                {
                    "completed_uids": sorted(self._completed_uids),
                    "token_diagnostics": self.client.token_diagnostics,
                    "students_meta": students_meta,
                }
            )
        except Exception as err:
            _LOGGER.debug("Todo store save skipped: %s", err)

    @callback
    def _on_diag_updated(self, _diag: dict[str, Any]) -> None:
        """Фоновая запись обновлённой диагностики токена в Store."""
        self.hass.async_create_task(self._async_persist_store())

    def is_item_completed(self, uid: str) -> bool:
        """Проверяет, отмечен ли элемент (ДЗ или урок) как выполненный в Home Assistant."""
        return uid in self._completed_uids

    async def async_set_item_completed(
        self, uid: str, completed: bool
    ) -> None:
        """Обновляет статус выполнения элемента в списке Todo и сохраняет его на диск."""
        if completed:
            self._completed_uids.add(uid)
        else:
            self._completed_uids.discard(uid)

        self.async_update_listeners()
        await self._async_persist_store()

    def tr_common(self, key: str, **kwargs: Any) -> str:
        """Возвращает локализованную строку из секции common."""
        common = self._translations.get("common", {})
        template = str(common.get(key, key))
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def tr_list(self, key: str) -> list[str]:
        """Возвращает список строк из секции common (разделитель '|')."""
        raw = self.tr_common(key)
        return [item.strip() for item in raw.split("|") if item.strip()]

    def tr_log(self, key: str, **kwargs: Any) -> str:
        """Форматирует сообщение лога из секции common."""
        return self.tr_common(key, **kwargs)

    def tr_entity_name(self, platform: str, key: str) -> str:
        """Возвращает локализованное имя сущности из секции entity."""
        ent_sec = self._translations.get("entity", {}).get(platform, {})
        val = ent_sec.get(key, {}).get("name")
        return str(val) if val else key

    @callback
    def _on_token_refreshed(
        self, new_token: str, fallback_token: str
    ) -> None:
        """Сохраняет проверенный обновлённый X-JWT-Token и резервный токен в ConfigEntry.data без перезагрузки."""
        if not new_token:
            return
        if (
            new_token == self.entry.data.get(CONF_TOKEN)
            and fallback_token == self.entry.data.get(CONF_FALLBACK_TOKEN)
        ):
            return
        new_data = {
            **self.entry.data,
            CONF_TOKEN: new_token,
            CONF_FALLBACK_TOKEN: fallback_token or new_token,
        }
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        _LOGGER.debug("%s", self.tr_log("log_token_refreshed"))

    @property
    def device_info(self) -> dict[str, Any]:
        """Описание основного (общего) устройства аккаунта."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.entry.title,
            manufacturer=self.tr_common("device_manufacturer"),
            model=self.tr_common("device_model_main"),
            configuration_url="https://dnevnik2.petersburgedu.ru",
        )

    def device_info_for_student(self, student: StudentData) -> dict[str, Any]:
        """Описание подустройства конкретного ученика."""
        sub_title = self.tr_common(
            "student_device_name",
            student_name=student.first_name,
        )
        model_parts = [p for p in (student.institution_name, student.group_name) if p]
        model_str = (
            " — ".join(model_parts)
            if model_parts
            else self.tr_common("device_model_student")
        )
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_student_{student.education_id}")},
            "name": sub_title,
            "manufacturer": self.tr_common("device_manufacturer"),
            "model": model_str,
            "configuration_url": "https://dnevnik2.petersburgedu.ru",
        }
        return info

    @property
    def students(self) -> dict[str, StudentData]:
        """Текущий словарь учеников по education_id."""
        return self.data or {}

    @property
    def known_students(self) -> dict[str, StudentData]:
        """Словарь учеников (актуальный или восстановленный из кэша при сбое портала на старте)."""
        return self.data or self._cached_students

    async def _async_update_data(self) -> dict[str, StudentData]:
        """Опрашивает API дневника и обновляет данные по каждому ученику."""
        try:
            children_raw = await self.client.async_get_children()
        except (Dnevnik2AuthError, Dnevnik2ConnectionError):
            self.client.replace_session(self._make_http_session())
            try:
                children_raw = await self.client.async_get_children()
            except Dnevnik2AuthError as err:
                self._consecutive_auth_failures += 1
                if self._consecutive_auth_failures >= 3:
                    raise ConfigEntryAuthFailed(
                        self.tr_common("error_auth_expired")
                    ) from err
                raise UpdateFailed(str(err)) from err
            except Dnevnik2ConnectionError as err:
                raise UpdateFailed(str(err)) from err

        self._consecutive_auth_failures = 0
        students = self._parse_students(children_raw, [])
        if any(not st.institution_name for st in students.values()):
            try:
                claims_raw = await self.client.async_get_claims()
            except Exception as err:
                _LOGGER.debug("Claims fetch skipped: %s", err)
                claims_raw = []
            if claims_raw:
                students = self._parse_students(children_raw, claims_raw)
        now_spb = datetime.now(SPB_TZ)
        today_spb = now_spb.date()
        period_start = today_spb - timedelta(days=90)
        period_end = today_spb + timedelta(days=7)

        for student in students.values():
            await self._populate_student_details(
                student,
                today_spb=today_spb,
                period_start=period_start,
                period_end=period_end,
            )

        self._cached_students = students
        await self._async_persist_store()
        self._prune_completed_uids(students)
        if self._previous_students is not None:
            self._emit_change_events(self._previous_students, students)
        else:
            self._init_low_balance_state(students)
        self._previous_students = students
        return students

    @callback
    def _init_low_balance_state(
        self, students: dict[str, StudentData]
    ) -> None:
        """Фиксирует стартовое состояние балансов при загрузке интеграции."""
        limit = float(self.balance_limit)
        if limit <= 0:
            self._low_balance_alerted.clear()
            return
        for edu_id, st in students.items():
            for acc_key, val in (
                ("hot", st.meal_hot_balance),
                ("buffet", st.meal_buffet_balance),
            ):
                if val is not None and val < limit:
                    self._low_balance_alerted[(edu_id, acc_key)] = val

    @callback
    def _emit_low_balance_events(
        self,
        prev_map: dict[str, StudentData] | None,
        curr_map: dict[str, StudentData],
    ) -> None:
        """Генерирует событие dnevnik2_low_balance при снижении баланса Столовой или Буфета ниже лимита."""
        limit = float(self.balance_limit)
        if limit <= 0:
            self._low_balance_alerted.clear()
            return

        for edu_id, curr in curr_map.items():
            prev = prev_map.get(edu_id) if prev_map else None
            dev_id = self.student_device_ids.get(edu_id)
            checks = (
                (
                    "hot",
                    "meal_hot_balance",
                    curr.meal_hot_balance,
                    prev.meal_hot_balance if prev else None,
                ),
                (
                    "buffet",
                    "meal_buffet_balance",
                    curr.meal_buffet_balance,
                    prev.meal_buffet_balance if prev else None,
                ),
            )
            for acc_key, sensor_key, cur_val, prev_val in checks:
                if cur_val is None:
                    continue
                alert_key = (edu_id, acc_key)
                if cur_val >= limit:
                    self._low_balance_alerted.pop(alert_key, None)
                    continue

                last_alerted = self._low_balance_alerted.get(alert_key)
                crossed_down = prev_val is not None and prev_val >= limit
                dropped_further = (
                    last_alerted is not None and cur_val < last_alerted
                )
                if (
                    last_alerted is None
                    or crossed_down
                    or dropped_further
                ):
                    self._low_balance_alerted[alert_key] = cur_val
                    self.hass.bus.async_fire(
                        EVENT_LOW_BALANCE,
                        {
                            "entry_id": self.entry.entry_id,
                            "device_id": dev_id,
                            "education_id": edu_id,
                            "first_name": curr.first_name,
                            "short_name": curr.short_name,
                            "full_name": curr.full_name,
                            "institution_name": curr.institution_name,
                            "group_name": curr.group_name,
                            "account": acc_key,
                            "account_name": self.tr_entity_name(
                                "sensor", sensor_key
                            ),
                            "balance": cur_val,
                            "previous_balance": prev_val,
                            "limit": self.balance_limit,
                            "hot_balance": curr.meal_hot_balance,
                            "buffet_balance": curr.meal_buffet_balance,
                        },
                    )

    def _prune_completed_uids(self, students: dict[str, StudentData]) -> None:
        """Оставляет в памяти только UID актуальных домашних заданий и уроков."""
        active_uids = {
            task.uid
            for st in students.values()
            for task in st.homework_tasks
        } | {
            lesson.uid
            for st in students.values()
            for lesson in st.lesson_tasks
        }
        self._completed_uids &= active_uids

    @callback
    def _emit_change_events(
        self,
        prev_map: dict[str, StudentData],
        curr_map: dict[str, StudentData],
    ) -> None:
        """Генерирует события dnevnik2_new_grade и dnevnik2_turnstile при появлении новых данных."""
        for edu_id, curr in curr_map.items():
            prev = prev_map.get(edu_id)
            if prev is None:
                continue
            dev_id = self.student_device_ids.get(edu_id)

            prev_grade_sig = (
                prev.last_grade,
                prev.last_grade_attributes.get("date"),
                prev.last_grade_attributes.get("work_type"),
                prev.grades_count,
            )
            curr_grade_sig = (
                curr.last_grade,
                curr.last_grade_attributes.get("date"),
                curr.last_grade_attributes.get("work_type"),
                curr.grades_count,
            )
            if curr.last_grade and curr_grade_sig != prev_grade_sig:
                self.hass.bus.async_fire(
                    EVENT_NEW_GRADE,
                    {
                        "entry_id": self.entry.entry_id,
                        "device_id": dev_id,
                        "education_id": edu_id,
                        "first_name": curr.first_name,
                        "short_name": curr.short_name,
                        "full_name": curr.full_name,
                        "institution_name": curr.institution_name,
                        "group_name": curr.group_name,
                        "last_grade": curr.last_grade,
                        "value": curr.last_grade_attributes.get("value"),
                        "subject": curr.last_grade_attributes.get("subject"),
                        "date": curr.last_grade_attributes.get("date"),
                        "work_type": curr.last_grade_attributes.get(
                            "work_type"
                        ),
                        "comment": curr.last_grade_attributes.get("comment"),
                        "average_grade": curr.average_grade,
                    },
                )

            if curr.last_turnstile_event and (
                curr.last_turnstile_event != prev.last_turnstile_event
                or curr.at_school != prev.at_school
            ):
                self.hass.bus.async_fire(
                    EVENT_TURNSTILE,
                    {
                        "entry_id": self.entry.entry_id,
                        "device_id": dev_id,
                        "education_id": edu_id,
                        "first_name": curr.first_name,
                        "short_name": curr.short_name,
                        "full_name": curr.full_name,
                        "institution_name": curr.institution_name,
                        "group_name": curr.group_name,
                        "at_school": curr.at_school,
                        "direction": curr.turnstile_attributes.get("direction"),
                        "datetime": curr.last_turnstile_event,
                    },
                )

        self._emit_low_balance_events(prev_map, curr_map)

    def file_download_signature(self, file_uuid: str) -> str:
        """Вычисляет HMAC-подпись для безопасного скачивания файла через локальный прокси HA."""
        secret = self.entry.entry_id.encode("utf-8")
        msg = str(file_uuid or "").strip().encode("utf-8")
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:16]

    def _extract_task_files(
        self, source: dict[str, Any]
    ) -> list[HomeworkFile]:
        """Извлекает прикреплённые учителем файлы из объекта задания или урока."""
        raw_files = source.get("files")
        if not isinstance(raw_files, list):
            raw_files = source.get("attachments")
        if not isinstance(raw_files, list):
            return []

        default_name = self.tr_common("file_default_name") or "File"
        extracted: list[HomeworkFile] = []
        seen_keys: set[str] = set()
        for f_obj in raw_files:
            if not isinstance(f_obj, dict):
                continue
            f_name = (
                _pick_str(f_obj, "file_name", "name", "filename", "title")
                or default_name
            )
            f_uuid = _pick_str(f_obj, "uuid", "file_uuid", "p_uuid")
            direct_url = ""
            proxy_url = ""
            if f_uuid:
                direct_url = f"{BASE_URL}{EP_FILEKIT_DOWNLOAD}?p_uuid={f_uuid}"
                sig = self.file_download_signature(f_uuid)
                proxy_url = (
                    f"/api/{DOMAIN}/file/{self.entry.entry_id}/{f_uuid}"
                    f"?sig={sig}&name={quote(f_name)}"
                )
            else:
                raw_url = _pick_str(f_obj, "url", "path", "link", "href")
                if raw_url:
                    direct_url = (
                        raw_url
                        if raw_url.startswith("http")
                        else f"{BASE_URL}{raw_url}"
                        if raw_url.startswith("/")
                        else ""
                    )
                    proxy_url = direct_url

            dedup_key = f_uuid or direct_url or f_name
            if not dedup_key or dedup_key in seen_keys:
                continue
            if not direct_url and not f_uuid:
                continue
            seen_keys.add(dedup_key)
            extracted.append(
                HomeworkFile(
                    name=f_name,
                    uuid=f_uuid,
                    url=direct_url,
                    proxy_url=proxy_url or direct_url,
                )
            )
        return extracted

    @staticmethod
    def _format_homework_line(task: HomeworkTask) -> str:
        """Форматирует одну строку домашнего задания со ссылками на прикреплённые файлы."""
        base = (
            f"• [{task.date_str}] {task.subject}: {task.task}"
            if task.task
            else f"• [{task.date_str}] {task.subject}"
        )
        if not task.files:
            return base
        links = ", ".join(f"📎 [{f.name}]({f.url})" for f in task.files)
        return f"{base} ({links})"

    def _build_homework_attributes(
        self, tasks: list[HomeworkTask]
    ) -> dict[str, Any]:
        """Формирует готовый текстовый атрибут и список заданий для сенсора ДЗ."""
        if not tasks:
            text = self.tr_common("no_homework_text")
        else:
            lines = [self._format_homework_line(t) for t in tasks]
            text = "\n".join(lines)
        return {
            "text": text,
            "tasks": [
                {
                    "date": t.date_str,
                    "subject": t.subject,
                    "task": t.task,
                    "files": [
                        {
                            "name": f.name,
                            "uuid": f.uuid,
                            "url": f.url,
                            "proxy_url": f.proxy_url,
                        }
                        for f in t.files
                    ],
                }
                for t in tasks
            ],
        }

    def _build_lessons_attributes(
        self, today_str: str, lessons: list[LessonTask]
    ) -> dict[str, Any]:
        """Формирует готовый текстовый атрибут и структуру уроков для сенсора расписания."""
        if not lessons:
            text = self.tr_common("no_lessons_text")
        else:
            room_lbl = self.tr_common("room_short")
            lines: list[str] = []
            for item in lessons:
                time_part = (
                    f" {item.time_from}–{item.time_to}"
                    if item.time_from and item.time_to
                    else ""
                )
                extra_parts = []
                if item.room:
                    extra_parts.append(f"{room_lbl} {item.room}")
                if item.teacher:
                    extra_parts.append(item.teacher)
                suffix = f" ({', '.join(extra_parts)})" if extra_parts else ""
                lines.append(
                    f"{item.number}.{time_part} — {item.subject}{suffix}"
                )
            text = "\n".join(lines)
        return {
            "date": today_str,
            "text": text,
            "lessons": [
                {
                    "number": item.number,
                    "subject": item.subject,
                    "time_from": item.time_from,
                    "time_to": item.time_to,
                    "room": item.room,
                    "teacher": item.teacher,
                }
                for item in lessons
            ],
        }

    def build_homework_extra_attributes(
        self, student: StudentData
    ) -> dict[str, Any]:
        """Возвращает атрибуты ДЗ с динамическим списком невыполненных заданий (и для sensor, и для todo)."""
        tasks = student.homework_tasks
        uncompleted = [
            t for t in tasks if not self.is_item_completed(t.uid)
        ]
        if not tasks:
            all_text = self.tr_common("no_homework_text")
        else:
            all_text = "\n".join(self._format_homework_line(t) for t in tasks)

        if not uncompleted:
            uncompleted_text = self.tr_common("no_homework_text")
        else:
            uncompleted_text = "\n".join(
                self._format_homework_line(t) for t in uncompleted
            )

        return {
            "first_name": student.first_name,
            "uncompleted_count": len(uncompleted),
            "text": all_text,
            "uncompleted_text": uncompleted_text,
            "tasks": [
                {
                    "date": t.date_str,
                    "subject": t.subject,
                    "task": t.task,
                    "completed": self.is_item_completed(t.uid),
                    "files": [
                        {
                            "name": f.name,
                            "uuid": f.uuid,
                            "url": f.url,
                            "proxy_url": f.proxy_url,
                        }
                        for f in t.files
                    ],
                }
                for t in tasks
            ],
        }

    def build_lessons_extra_attributes(
        self, student: StudentData
    ) -> dict[str, Any]:
        """Возвращает атрибуты расписания уроков (и для sensor, и для todo)."""
        attrs = dict(student.schedule_today_attributes)
        attrs["first_name"] = student.first_name
        return attrs

    def _parse_students(
        self,
        children_raw: list[dict[str, Any]],
        claims_raw: list[dict[str, Any]],
    ) -> dict[str, StudentData]:
        """Извлекает список учеников из related-child-list и claim/list."""
        claims_by_fio: dict[str, str] = {}
        for claim in claims_raw:
            fio = _pick_str(claim, "child_fio", "fio")
            inst = _pick_str(claim, "institution_name", "short_name")
            if fio and inst:
                claims_by_fio[fio.lower()] = inst

        result: dict[str, StudentData] = {}
        for child in children_raw:
            full_name, short_name, first_name = _build_full_name(child)
            identity = child.get("identity")
            person_id = (
                _pick_str(identity, "id")
                if isinstance(identity, dict)
                else _pick_str(child, "person_id", "id")
            )
            hash_uid = _pick_str(child, "hash_uid", "uid")
            educations = child.get("educations")
            if isinstance(educations, list) and educations:
                for edu in educations:
                    if not isinstance(edu, dict):
                        continue
                    edu_id = _pick_str(edu, "education_id", "id")
                    if not edu_id:
                        continue
                    inst_name = (
                        _pick_str(
                            edu,
                            "institution_name",
                            "institution_short_name",
                            "school_name",
                        )
                        or claims_by_fio.get(full_name.lower(), "")
                    )
                    group_name = normalize_group_name(
                        _pick_str(
                            edu, "group_name", "class_name", "classname"
                        )
                    )
                    group_id = _pick_str(edu, "group_id", "class_id") or None
                    result[edu_id] = StudentData(
                        education_id=edu_id,
                        person_id=person_id or edu_id,
                        full_name=full_name,
                        short_name=short_name,
                        first_name=first_name,
                        institution_name=inst_name,
                        group_name=group_name,
                        group_id=group_id,
                        hash_uid=hash_uid or _pick_str(edu, "hash_uid", "uid"),
                    )
            else:
                edu_id = _pick_str(child, "education_id", "id")
                if edu_id:
                    inst_name = (
                        _pick_str(child, "institution_name", "school_name")
                        or claims_by_fio.get(full_name.lower(), "")
                    )
                    group_name = normalize_group_name(
                        _pick_str(child, "group_name", "class_name")
                    )
                    group_id = _pick_str(child, "group_id") or None
                    result[edu_id] = StudentData(
                        education_id=edu_id,
                        person_id=person_id or edu_id,
                        full_name=full_name,
                        short_name=short_name,
                        first_name=first_name,
                        institution_name=inst_name,
                        group_name=group_name,
                        group_id=group_id,
                        hash_uid=hash_uid,
                    )

        return result

    async def _resolve_student_period(
        self,
        student: StudentData,
        today_spb: date,
        fallback_start: date,
    ) -> tuple[date, date]:
        """Определяет текущий учебный период (четверть/триместр/полугодие) по group_id ученика."""
        group_id = student.group_id
        if not group_id:
            return fallback_start, today_spb

        periods_raw: list[dict[str, Any]] = []
        cached = self._group_periods_cache.get(str(group_id))
        if cached and cached[0] == today_spb:
            periods_raw = cached[1]
        else:
            try:
                periods_raw = await self.client.async_get_periods(group_id)
                if periods_raw:
                    self._group_periods_cache[str(group_id)] = (
                        today_spb,
                        periods_raw,
                    )
            except Exception as err:
                _LOGGER.debug(
                    "Periods fetch skipped for group %s: %s", group_id, err
                )
                if cached:
                    periods_raw = cached[1]

        if not periods_raw:
            return fallback_start, today_spb

        year_kw = self.tr_list("year_period_keywords")
        parsed: list[dict[str, Any]] = []
        for item in periods_raw:
            if not isinstance(item, dict):
                continue
            name = _pick_str(item, "name", "title", "period_name")
            d_from = _parse_lesson_date(
                _pick_str(
                    item,
                    "date_from",
                    "date_start",
                    "start_date",
                    "datetime_from",
                )
            )
            d_to = _parse_lesson_date(
                _pick_str(
                    item, "date_to", "date_end", "end_date", "datetime_to"
                )
            )
            if not name or d_from is None or d_to is None or d_from > d_to:
                continue
            duration = (d_to - d_from).days
            is_year = duration >= 200 or any(
                k in name.lower() for k in year_kw
            )
            parsed.append(
                {
                    "name": name,
                    "d_from": d_from,
                    "d_to": d_to,
                    "duration": duration,
                    "is_year": is_year,
                }
            )

        if not parsed:
            return fallback_start, today_spb

        parsed.sort(key=lambda p: (p["d_from"], p["duration"]))
        sub_year = [p for p in parsed if not p["is_year"] and p["duration"] >= 7]
        pool = sub_year if sub_year else parsed

        active = [
            p for p in pool if p["d_from"] <= today_spb <= p["d_to"]
        ]
        if active:
            chosen = min(active, key=lambda p: p["duration"])
        else:
            past = [p for p in pool if p["d_to"] < today_spb]
            if past:
                chosen = max(past, key=lambda p: (p["d_to"], -p["duration"]))
            else:
                chosen = min(pool, key=lambda p: (p["d_from"], p["duration"]))

        student.period_name = chosen["name"]
        student.period_start_str = chosen["d_from"].strftime("%d.%m.%Y")
        student.period_end_str = chosen["d_to"].strftime("%d.%m.%Y")
        student.period_days_left = max(0, (chosen["d_to"] - today_spb).days)
        student.periods_list = [
            {
                "name": p["name"],
                "date_from": p["d_from"].strftime("%d.%m.%Y"),
                "date_to": p["d_to"].strftime("%d.%m.%Y"),
                "is_current": p is chosen,
            }
            for p in parsed
        ]
        return chosen["d_from"], chosen["d_to"]

    async def _populate_student_details(
        self,
        student: StudentData,
        *,
        today_spb: date,
        period_start: date,
        period_end: date,
    ) -> None:
        """Заполняет оценки, расписание, ДЗ, СКУД и баланс питания для одного ученика."""
        edu_id = student.education_id
        active_start, active_end = await self._resolve_student_period(
            student, today_spb, period_start
        )
        marks_to = max(today_spb, active_end)

        try:
            marks_raw = await self.client.async_get_marks(
                edu_id, active_start, marks_to
            )
            self._apply_marks(
                student,
                marks_raw,
                today_spb,
                period_start=active_start,
                period_end=active_end,
            )
        except Exception as err:
            _LOGGER.debug("Marks fetch skipped for %s: %s", edu_id, err)

        cal_start = today_spb - timedelta(days=7)
        cal_end = max(period_end, today_spb + timedelta(days=14))
        lessons_raw: list[dict[str, Any]] = []
        try:
            lessons_raw = await self.client.async_get_lessons(
                edu_id, cal_start, cal_end
            )
            self._apply_lessons_homework(student, lessons_raw, today_spb)
        except Exception as err:
            _LOGGER.debug("Lessons fetch skipped for %s: %s", edu_id, err)

        try:
            schedule_raw = await self.client.async_get_schedule(
                edu_id, cal_start, cal_end
            )
            self._apply_schedule(
                student,
                schedule_raw,
                today_spb,
                lessons_raw=lessons_raw,
                window_start=cal_start,
                window_end=cal_end,
            )
        except Exception as err:
            _LOGGER.debug("Schedule fetch skipped for %s: %s", edu_id, err)

        try:
            acs_raw = await self.client.async_get_attendance(edu_id, limit=20)
            self._apply_attendance(student, acs_raw)
        except Exception as err:
            _LOGGER.debug("ACS fetch skipped for %s: %s", edu_id, err)

        try:
            meal_raw = await self.client.async_get_meal_balance(
                edu_id, student.hash_uid
            )
            self._apply_meal_balance(student, meal_raw)
        except Exception as err:
            _LOGGER.debug("Meal balance fetch skipped for %s: %s", edu_id, err)

    def _apply_marks(
        self,
        student: StudentData,
        marks_raw: list[dict[str, Any]],
        today_spb: date,
        *,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> None:
        numeric_grades: list[int] = []
        by_subject: dict[str, list[int]] = {}
        final_grades: dict[str, Any] = {}
        absences = 0
        lates = 0
        graded_rows: list[tuple[date, int, dict[str, Any], str]] = []
        today_grades: list[dict[str, Any]] = []
        today_seen_keys: set[str] = set()
        final_kw = self.tr_list("final_grade_keywords")

        edu_id = student.education_id
        known_set = self._known_grade_uids.get(edu_id)
        current_set: set[str] = set()
        detected_key = (edu_id, today_spb)
        for old_key in list(self._detected_today_grades):
            if old_key[0] == edu_id and old_key[1] != today_spb:
                self._detected_today_grades.pop(old_key, None)
        detected_list = self._detected_today_grades.setdefault(detected_key, [])

        for idx, row in enumerate(marks_raw):
            code = _pick_str(
                row,
                "estimate_type_code",
                "type_code",
                "estimate_value_code",
                "estimate_code",
                "code",
            )
            val_str = _pick_str(
                row,
                "estimate_value_name",
                "value_name",
                "value",
                "mark",
                "estimate_value",
            )
            date_str = _pick_str(
                row, "date", "date_estimate", "lesson_date"
            )
            mark_dt = _parse_lesson_date(date_str)
            in_period = True
            if mark_dt is not None:
                if period_start is not None and mark_dt < period_start:
                    in_period = False
                if period_end is not None and mark_dt > period_end:
                    in_period = False

            if code == ABSENCE_CODE:
                if in_period:
                    absences += 1
                continue
            if code == LATE_CODE:
                if in_period:
                    lates += 1
                continue
            if val_str.isdigit():
                grade_num = int(val_str)
                if 1 <= grade_num <= 5:
                    subj = _pick_str(row, "subject_name", "subject") or "—"
                    created_dt = _parse_lesson_date(
                        _pick_str(
                            row,
                            "created_at",
                            "date_create",
                            "create_date",
                            "datetime",
                        )
                    )
                    work_type = _pick_str(
                        row,
                        "estimate_type_name",
                        "type_name",
                        "work_type",
                        "type",
                    )
                    comment = _pick_str(row, "estimate_comment", "comment")
                    is_final = bool(
                        work_type
                        and final_kw
                        and any(k in work_type.lower() for k in final_kw)
                    )
                    if is_final:
                        final_grades[subj] = grade_num
                    elif in_period:
                        numeric_grades.append(grade_num)
                        by_subject.setdefault(subj, []).append(grade_num)

                    row_id = _pick_str(row, "id", "estimate_id") or str(idx)
                    grade_uid = f"{row_id}|{date_str}|{subj}|{val_str}|{work_type}"
                    current_set.add(grade_uid)

                    grade_entry = {
                        "value": grade_num,
                        "subject": subj,
                        "date": date_str,
                        "work_type": work_type,
                        "comment": comment,
                        "_uid": grade_uid,
                    }

                    if known_set is not None and grade_uid not in known_set:
                        if not any(
                            g.get("_uid") == grade_uid for g in detected_list
                        ):
                            detected_list.append(grade_entry)

                    if mark_dt == today_spb or created_dt == today_spb:
                        today_seen_keys.add(grade_uid)
                        today_grades.append(grade_entry)

                    graded_rows.append(
                        (mark_dt or date.min, idx, row, val_str)
                    )

        self._known_grade_uids[edu_id] = current_set

        for det in detected_list:
            uid = str(det.get("_uid") or "")
            if uid and uid not in today_seen_keys:
                today_seen_keys.add(uid)
                today_grades.append(det)

        clean_today_grades = [
            {k: v for k, v in item.items() if k != "_uid"}
            for item in today_grades
        ]
        if clean_today_grades:
            lines: list[str] = []
            for g in clean_today_grades:
                details = [
                    p for p in (g.get("work_type"), g.get("comment")) if p
                ]
                suffix = f" ({' — '.join(details)})" if details else ""
                lines.append(f"• {g['subject']}: {g['value']}{suffix}")
            today_text = "\n".join(lines)
        else:
            today_text = self.tr_common("no_grades_today_text")

        student.grades_count = len(numeric_grades)
        student.absences_count = absences
        student.lates_count = lates
        student.final_grades = dict(sorted(final_grades.items()))
        if numeric_grades:
            student.average_grade = round(
                sum(numeric_grades) / len(numeric_grades), 2
            )
            student.subject_averages = {
                subj: round(sum(vals) / len(vals), 2)
                for subj, vals in sorted(by_subject.items())
            }
        if graded_rows:
            graded_rows.sort(key=lambda item: (item[0], item[1]))
            _, _, latest_item, latest_val_str = graded_rows[-1]
            subj = _pick_str(latest_item, "subject_name", "subject")
            date_str = _pick_str(
                latest_item, "date", "date_estimate", "lesson_date"
            )
            work_type = _pick_str(
                latest_item,
                "estimate_type_name",
                "type_name",
                "work_type",
                "type",
            )
            comment = _pick_str(latest_item, "estimate_comment", "comment")
            student.last_grade = (
                f"{latest_val_str} ({subj})" if subj else latest_val_str
            )
            student.last_grade_attributes = {
                "value": int(latest_val_str),
                "subject": subj,
                "date": date_str,
                "work_type": work_type,
                "comment": comment,
                "today_count": len(clean_today_grades),
                "today_text": today_text,
                "today_grades": clean_today_grades,
            }
        else:
            student.last_grade_attributes = {
                "today_count": 0,
                "today_text": today_text,
                "today_grades": [],
            }

    def _apply_lessons_homework(
        self,
        student: StudentData,
        lessons_raw: list[dict[str, Any]],
        today_spb: date,
    ) -> None:
        homework_tasks: list[HomeworkTask] = []
        seen_uids: set[str] = set()

        for row in lessons_raw:
            lesson_date_raw = _pick_str(
                row, "date", "datetime_from", "lesson_date", "date_from"
            )
            due_dt = _parse_lesson_date(lesson_date_raw)
            if due_dt is None or due_dt < today_spb:
                continue
            subj = _pick_str(row, "subject_name", "subject", "name") or "—"
            tasks = row.get("tasks")
            extracted_entries: list[tuple[str, list[HomeworkFile]]] = []
            if isinstance(tasks, list) and tasks:
                for task_obj in tasks:
                    if not isinstance(task_obj, dict):
                        continue
                    task_text = _pick_str(
                        task_obj,
                        "task_name",
                        "task",
                        "name",
                        "text",
                        "description",
                    )
                    task_files = self._extract_task_files(task_obj)
                    if task_text or task_files:
                        extracted_entries.append((task_text, task_files))
            else:
                hw_text = _pick_str(
                    row,
                    "task",
                    "homework",
                    "hometask",
                    "lesson_task",
                    "task_name",
                )
                row_files = self._extract_task_files(row)
                if hw_text or row_files:
                    extracted_entries.append((hw_text, row_files))

            for text, files in extracted_entries:
                uid_detail = text or "|".join(
                    f.uuid or f.url or f.name for f in files
                )
                uid = make_item_uid(
                    "hw", student.education_id, due_dt, subj, uid_detail
                )
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)
                homework_tasks.append(
                    HomeworkTask(
                        uid=uid,
                        subject=subj,
                        task=text,
                        due=due_dt,
                        date_str=due_dt.strftime("%d.%m.%Y"),
                        files=files,
                    )
                )

        homework_tasks.sort(key=lambda item: (item.due, item.subject))
        student.homework_tasks = homework_tasks
        student.homework_count = len(homework_tasks)
        student.homework_attributes = self._build_homework_attributes(
            homework_tasks
        )

    def _parse_schedule_rows(
        self,
        education_id: str,
        schedule_raw: list[dict[str, Any]],
        lessons_raw: list[dict[str, Any]] | None = None,
        hw_by_date_subj: dict[tuple[date, str], str] | None = None,
    ) -> list[LessonTask]:
        """Преобразует сырые строки расписания и проведённых уроков в отсортированный список LessonTask."""
        merged_by_key: dict[tuple[date, str, str], LessonTask] = {}

        all_sources: list[dict[str, Any]] = list(schedule_raw)
        if lessons_raw:
            all_sources.extend(lessons_raw)

        for idx, row in enumerate(all_sources, start=1):
            if not isinstance(row, dict):
                continue
            row_date_raw = _pick_str(
                row, "date", "datetime_from", "lesson_date", "date_from"
            )
            row_dt = _parse_lesson_date(row_date_raw)
            if row_dt is None:
                continue
            subj = _pick_str(row, "subject_name", "subject", "name") or "—"
            num = (
                _pick_str(row, "number", "lesson_number", "order", "position")
                or str(idx)
            )
            time_from = _extract_hhmm(
                _pick_str(
                    row, "datetime_from", "time_from", "start_time", "time_start"
                )
            )
            time_to = _extract_hhmm(
                _pick_str(row, "datetime_to", "time_to", "end_time", "time_end")
            )
            room = _pick_str(
                row, "office", "cabinet", "room", "place_name", "office_name"
            )
            teacher = _pick_str(
                row, "teacher_name", "teacher", "teachers_name", "employee_name"
            )
            hw_text = (
                hw_by_date_subj.get((row_dt, subj), "")
                if hw_by_date_subj
                else ""
            )
            if not hw_text:
                tasks = row.get("tasks")
                if isinstance(tasks, list) and tasks:
                    parts = [
                        _pick_str(
                            t,
                            "task_name",
                            "task",
                            "name",
                            "text",
                            "description",
                        )
                        for t in tasks
                        if isinstance(t, dict)
                    ]
                    hw_text = "; ".join(p for p in parts if p)
                else:
                    hw_text = _pick_str(
                        row,
                        "task",
                        "homework",
                        "hometask",
                        "lesson_task",
                        "task_name",
                    )

            dedup_key = (row_dt, num, subj)
            existing = merged_by_key.get(dedup_key)
            if existing is not None:
                if not existing.time_from and time_from:
                    existing.time_from = time_from
                if not existing.time_to and time_to:
                    existing.time_to = time_to
                if not existing.room and room:
                    existing.room = room
                if not existing.teacher and teacher:
                    existing.teacher = teacher
                if not existing.homework_text and hw_text:
                    existing.homework_text = hw_text
                continue

            uid = make_item_uid(
                "lsn",
                education_id,
                row_dt,
                f"{num}:{subj}",
                time_from,
            )
            merged_by_key[dedup_key] = LessonTask(
                uid=uid,
                number=num,
                subject=subj,
                time_from=time_from,
                time_to=time_to,
                room=room,
                teacher=teacher,
                due=row_dt,
                date_str=row_dt.strftime("%d.%m.%Y"),
                homework_text=hw_text,
            )

        items = list(merged_by_key.values())
        items.sort(
            key=lambda item: (
                item.due,
                int(item.number) if item.number.isdigit() else 99,
                item.time_from,
            )
        )
        return items

    def _apply_schedule(
        self,
        student: StudentData,
        schedule_raw: list[dict[str, Any]],
        today_spb: date,
        *,
        lessons_raw: list[dict[str, Any]] | None = None,
        window_start: date | None = None,
        window_end: date | None = None,
    ) -> None:
        today_str = today_spb.strftime("%d.%m.%Y")
        hw_by_date_subj: dict[tuple[date, str], str] = {}
        for hw in student.homework_tasks:
            key = (hw.due, hw.subject)
            if hw.task and key not in hw_by_date_subj:
                hw_by_date_subj[key] = hw.task

        all_lessons = self._parse_schedule_rows(
            student.education_id,
            schedule_raw,
            lessons_raw=lessons_raw,
            hw_by_date_subj=hw_by_date_subj,
        )
        lesson_tasks = [
            item for item in all_lessons if item.due == today_spb
        ]
        student.lesson_tasks = lesson_tasks
        student.calendar_lessons = all_lessons
        student.calendar_window_start = window_start
        student.calendar_window_end = window_end
        student.lessons_today_count = len(lesson_tasks)
        student.schedule_today_attributes = self._build_lessons_attributes(
            today_str, lesson_tasks
        )

    async def async_get_calendar_lessons(
        self, education_id: str, start_date: date, end_date: date
    ) -> list[LessonTask]:
        """Возвращает уроки расписания для календаря за произвольный диапазон дат."""
        st = self.students.get(education_id)
        if (
            st is not None
            and st.calendar_window_start is not None
            and st.calendar_window_end is not None
            and st.calendar_window_start <= start_date
            and end_date <= st.calendar_window_end
            and st.calendar_lessons
        ):
            return [
                item
                for item in st.calendar_lessons
                if start_date <= item.due <= end_date
            ]

        try:
            schedule_raw = await self.client.async_get_schedule(
                education_id, start_date, end_date
            )
        except Exception:
            schedule_raw = []
        try:
            lessons_raw = await self.client.async_get_lessons(
                education_id, start_date, end_date
            )
        except Exception:
            lessons_raw = []

        parsed = self._parse_schedule_rows(
            education_id, schedule_raw, lessons_raw=lessons_raw
        )
        return [
            item for item in parsed if start_date <= item.due <= end_date
        ]

    def _apply_attendance(
        self, student: StudentData, acs_raw: list[dict[str, Any]]
    ) -> None:
        if not acs_raw:
            return
        in_prefixes = tuple(self.tr_list("direction_in_prefixes")) or (
            "in",
            "enter",
            "1",
        )
        out_prefixes = tuple(self.tr_list("direction_out_prefixes")) or (
            "out",
            "exit",
            "2",
        )

        sortable: list[tuple[datetime, dict[str, Any]]] = []
        for idx, row in enumerate(acs_raw):
            raw_time = _pick_str(
                row, "datetime", "date_time", "date", "time", "created_at"
            )
            dt_val = _parse_datetime(raw_time) or (
                datetime.min + timedelta(seconds=len(acs_raw) - idx)
            )
            sortable.append((dt_val, row))

        sortable.sort(key=lambda item: item[0], reverse=True)
        sorted_rows = [item[1] for item in sortable]

        first = sorted_rows[0]
        direction_raw = _pick_str(
            first, "direction", "event_type", "type", "action"
        )
        direction_low = direction_raw.lower()
        event_time = _pick_str(
            first, "datetime", "date_time", "date", "time", "created_at"
        )
        is_in: bool | None = None
        if direction_low.startswith(in_prefixes):
            is_in = True
        elif direction_low.startswith(out_prefixes):
            is_in = False

        student.at_school = is_in
        student.last_turnstile_event = event_time or None
        student.turnstile_attributes = {
            "direction": direction_raw,
            "at_school": is_in,
            "recent_events": [
                {
                    "datetime": _pick_str(
                        r, "datetime", "date_time", "date", "time"
                    ),
                    "direction": _pick_str(
                        r, "direction", "event_type", "type"
                    ),
                }
                for r in sorted_rows[:10]
            ],
        }

    def _apply_meal_balance(
        self, student: StudentData, meal_raw: dict[str, Any]
    ) -> None:
        if not meal_raw:
            return

        accounts = meal_raw.get("accounts")
        if isinstance(accounts, list) and accounts:
            total_sum = 0.0
            has_numeric = False
            parsed_accounts: list[dict[str, Any]] = []
            by_type: dict[str, float] = {}
            customer_id = ""
            hot_val: float | None = None
            buffet_val: float | None = None
            hot_name = ""
            buffet_name = ""
            unmatched: list[tuple[str, float]] = []

            hot_kw = self.tr_list("meal_hot_keywords")
            buf_kw = self.tr_list("meal_buffet_keywords")

            for acc in accounts:
                if not isinstance(acc, dict):
                    continue
                acc_name = _pick_str(
                    acc, "accounttypename", "name", "type", "title"
                )
                raw_sum = acc.get("sum")
                if raw_sum is None:
                    raw_sum = acc.get("balance")
                val_float: float | None = None
                if isinstance(raw_sum, (int, float)) and not isinstance(
                    raw_sum, bool
                ):
                    val_float = round(float(raw_sum), 2)
                elif isinstance(raw_sum, str):
                    try:
                        val_float = round(
                            float(raw_sum.replace(",", ".").strip()), 2
                        )
                    except ValueError:
                        val_float = None

                if val_float is not None:
                    total_sum += val_float
                    has_numeric = True
                    if acc_name:
                        by_type[acc_name] = val_float
                        low_name = acc_name.lower()
                        if any(k in low_name for k in buf_kw):
                            buffet_val = val_float
                            buffet_name = acc_name
                            by_type["buffet_balance"] = val_float
                        elif any(k in low_name for k in hot_kw):
                            hot_val = val_float
                            hot_name = acc_name
                            by_type["hot_balance"] = val_float
                        else:
                            unmatched.append((acc_name, val_float))
                    else:
                        unmatched.append(("", val_float))

                cust = _pick_str(acc, "customer_name", "id")
                if cust and not customer_id:
                    customer_id = cust

                parsed_accounts.append(
                    {
                        "id": _pick_str(acc, "id"),
                        "name": acc_name,
                        "balance": val_float,
                        "customer": _pick_str(acc, "customer_name"),
                    }
                )

            for u_name, u_val in unmatched:
                if hot_val is None:
                    hot_val = u_val
                    hot_name = u_name
                    by_type["hot_balance"] = u_val
                elif buffet_val is None:
                    buffet_val = u_val
                    buffet_name = u_name
                    by_type["buffet_balance"] = u_val

            if has_numeric:
                student.meal_balance = round(total_sum, 2)
                student.meal_hot_balance = hot_val
                student.meal_buffet_balance = buffet_val
                base_attrs: dict[str, Any] = {
                    "total_balance": round(total_sum, 2),
                    "hot_balance": hot_val,
                    "buffet_balance": buffet_val,
                    "accounts": parsed_accounts,
                }
                if customer_id:
                    base_attrs["account_number"] = customer_id
                base_attrs.update(by_type)
                student.meal_attributes = base_attrs
                student.meal_hot_attributes = {
                    "account_type": hot_name,
                    **base_attrs,
                }
                student.meal_buffet_attributes = {
                    "account_type": buffet_name,
                    **base_attrs,
                }
                return

        items = (
            meal_raw.get("items")
            if isinstance(meal_raw.get("items"), list)
            else []
        )
        source = (
            items[0] if items and isinstance(items[0], dict) else meal_raw
        )
        for key in (
            "hot_balance",
            "balance",
            "total_balance",
            "amount",
            "sum",
        ):
            val = source.get(key)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                student.meal_balance = round(float(val), 2)
                student.meal_hot_balance = student.meal_balance
                break
            if isinstance(val, str):
                try:
                    student.meal_balance = round(
                        float(val.replace(",", ".").strip()), 2
                    )
                    student.meal_hot_balance = student.meal_balance
                    break
                except ValueError:
                    continue
        raw_buf = source.get("buffet_balance")
        if isinstance(raw_buf, (int, float)) and not isinstance(raw_buf, bool):
            student.meal_buffet_balance = round(float(raw_buf), 2)
        elif isinstance(raw_buf, str):
            try:
                student.meal_buffet_balance = round(
                    float(raw_buf.replace(",", ".").strip()), 2
                )
            except ValueError:
                pass
        student.meal_attributes = {
            k: v
            for k, v in source.items()
            if isinstance(v, (str, int, float, bool))
            and k not in ("token", "zsign")
        }
        student.meal_hot_attributes = dict(student.meal_attributes)
        student.meal_buffet_attributes = dict(student.meal_attributes)
