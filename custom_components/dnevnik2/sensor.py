"""Платформа сенсоров для основного устройства и подустройств каждого ученика."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONN_STATE_AUTH_EXPIRED,
    CONN_STATE_PORTAL_ERROR,
    CONN_STATE_TIMEOUT,
    CONNECTION_STATES,
    DOMAIN,
    OUTPUT_MODE_SENSOR,
    REQUEST_TIMEOUT_SEC,
)
from .manager import SPB_TZ, Dnevnik2Coordinator, StudentData


def _fmt_unix_ts(ts: int | None) -> str | None:
    """Форматирует Unix-время в читаемую ISO-строку часового пояса Санкт-Петербурга."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=SPB_TZ).isoformat()
    except Exception:
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт сенсоры на основном устройстве и набор сенсоров на подустройстве каждого ученика."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        Dnevnik2AccountStatusSensor(coordinator, entry),
        Dnevnik2ConnectionStatusSensor(coordinator, entry),
    ]
    hw_as_sensor = coordinator.homework_mode == OUTPUT_MODE_SENSOR
    lessons_as_sensor = coordinator.lessons_mode == OUTPUT_MODE_SENSOR

    for edu_id in coordinator.known_students:
        entities.extend(
            [
                Dnevnik2AverageGradeSensor(coordinator, entry, edu_id),
                Dnevnik2LastGradeSensor(coordinator, entry, edu_id),
                Dnevnik2TurnstileLastSensor(coordinator, entry, edu_id),
                Dnevnik2MealHotBalanceSensor(coordinator, entry, edu_id),
                Dnevnik2MealBuffetBalanceSensor(coordinator, entry, edu_id),
            ]
        )
        if hw_as_sensor:
            entities.append(
                Dnevnik2HomeworkSensor(coordinator, entry, edu_id)
            )
        if lessons_as_sensor:
            entities.append(
                Dnevnik2LessonsTodaySensor(coordinator, entry, edu_id)
            )

    async_add_entities(entities)


class Dnevnik2AccountStatusSensor(
    CoordinatorEntity[Dnevnik2Coordinator], SensorEntity
):
    """Сенсор общего статуса аккаунта на основном устройстве."""

    _attr_has_entity_name = True
    _attr_translation_key = "account_status"
    _attr_icon = "mdi:school"

    def __init__(
        self, coordinator: Dnevnik2Coordinator, entry: ConfigEntry
    ) -> None:
        """Инициализация сенсора статуса аккаунта."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_account_status"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> int:
        """Количество подключённых учеников в аккаунте."""
        return len(self.coordinator.students)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Список учеников и их учебных заведений."""
        return {
            "students": [
                {
                    "education_id": st.education_id,
                    "name": st.short_name,
                    "institution": st.institution_name,
                    "group": st.group_name,
                }
                for st in self.coordinator.students.values()
            ]
        }


class Dnevnik2ConnectionStatusSensor(
    CoordinatorEntity[Dnevnik2Coordinator], SensorEntity
):
    """Диагностический сенсор состояния сессии и соединения с порталом на основном устройстве."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CONNECTION_STATES

    def __init__(
        self, coordinator: Dnevnik2Coordinator, entry: ConfigEntry
    ) -> None:
        """Инициализация диагностического сенсора сессии."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_connection_status"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Диагностический сенсор сессии всегда доступен, в том числе при сбоях портала."""
        return True

    @property
    def native_value(self) -> str:
        """Текущий статус соединения ('ok', 'portal_error', 'timeout', 'auth_expired')."""
        return self.coordinator.client.connection_state

    @property
    def icon(self) -> str:
        """Динамическая иконка состояния сессии."""
        state = self.coordinator.client.connection_state
        if state == CONN_STATE_PORTAL_ERROR:
            return "mdi:cloud-alert-outline"
        if state == CONN_STATE_TIMEOUT:
            return "mdi:cloud-clock-outline"
        if state == CONN_STATE_AUTH_EXPIRED:
            return "mdi:key-alert-outline"
        return "mdi:cloud-check-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Подробные диагностические атрибуты сессии, токена и таймаутов."""
        client = self.coordinator.client
        diag = client.token_diagnostics
        claims = diag.get("current_jwt_claims") or {}
        return {
            "last_success": _fmt_unix_ts(client.last_success_at),
            "last_error": client.last_error_message,
            "last_error_at": _fmt_unix_ts(client.last_error_at),
            "http_status": client.last_http_status,
            "token_issued_at": _fmt_unix_ts(claims.get("iat")),
            "token_ttl_sec": claims.get("ttl_seconds"),
            "has_sso_key": client.has_esk,
            "sso_refreshes": client.sso_refreshes_count,
            "scan_interval_min": self.coordinator.scan_interval_minutes,
            "request_timeout_sec": REQUEST_TIMEOUT_SEC,
        }


class _BaseStudentSensor(
    CoordinatorEntity[Dnevnik2Coordinator], SensorEntity
):
    """Базовый класс сенсора подустройства конкретного ученика."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
        key: str,
    ) -> None:
        """Привязывает сенсор к подустройству ученика."""
        super().__init__(coordinator)
        self._entry = entry
        self._edu_id = education_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_student_{education_id}_{key}"
        student = coordinator.known_students.get(education_id)
        if student is not None:
            self._attr_device_info = DeviceInfo(
                **coordinator.device_info_for_student(student)
            )

    @property
    def _student(self) -> StudentData | None:
        return self.coordinator.students.get(self._edu_id)


class Dnevnik2AverageGradeSensor(_BaseStudentSensor):
    """Средний балл ученика за текущий период."""

    _attr_icon = "dnevnik2:grade-avg"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора среднего балла."""
        super().__init__(coordinator, entry, education_id, "average_grade")

    @property
    def native_value(self) -> float | None:
        """Текущий средний балл."""
        st = self._student
        return st.average_grade if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Разбивка средних баллов по предметам, текущий период, итоговые оценки и статистика посещаемости."""
        st = self._student
        if not st:
            return {}
        attrs: dict[str, Any] = {
            "period_name": st.period_name or None,
            "period_start": st.period_start_str or None,
            "period_end": st.period_end_str or None,
            "period_days_left": st.period_days_left,
            "grades_count": st.grades_count,
            "absences_count": st.absences_count,
            "lates_count": st.lates_count,
            "subject_averages": st.subject_averages,
            "final_grades": st.final_grades,
        }
        if st.periods_list:
            attrs["periods"] = st.periods_list
        return attrs


class Dnevnik2LastGradeSensor(_BaseStudentSensor):
    """Последняя полученная оценка ученика."""

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора последней оценки."""
        super().__init__(coordinator, entry, education_id, "last_grade")

    @property
    def icon(self) -> str:
        """Штатная иконка оценки (mdi:numeric-5-box-outline .. 1)."""
        val = self.native_value or ""
        first = val.strip()[:1]
        if first in ("1", "2", "3", "4", "5"):
            return f"mdi:numeric-{first}-box-outline"
        return "mdi:numeric-5-box-outline"

    @property
    def native_value(self) -> str | None:
        """Строка вида '5 (Алгебра)'."""
        st = self._student
        return st.last_grade if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Детали последней оценки."""
        st = self._student
        return st.last_grade_attributes if st else {}


class Dnevnik2HomeworkSensor(_BaseStudentSensor):
    """Сенсор домашних заданий с готовым текстовым атрибутом (при выборе режима sensor)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора домашних заданий."""
        super().__init__(coordinator, entry, education_id, "homework")

    @property
    def icon(self) -> str:
        """Динамическая иконка ДЗ (книга с карандашом или с галочкой при 0 заданий)."""
        return (
            "dnevnik2:homework"
            if self.native_value > 0
            else "dnevnik2:homework-done"
        )

    @property
    def native_value(self) -> int:
        """Количество актуальных домашних заданий."""
        st = self._student
        return st.homework_count if st else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Готовый многострочный текст ('text', 'uncompleted_text') и список заданий ('tasks')."""
        st = self._student
        if not st:
            return {}
        return self.coordinator.build_homework_extra_attributes(st)


class Dnevnik2LessonsTodaySensor(_BaseStudentSensor):
    """Сенсор уроков сегодня с готовым текстовым атрибутом (при выборе режима sensor)."""

    _attr_icon = "dnevnik2:schedule"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора расписания."""
        super().__init__(coordinator, entry, education_id, "lessons_today")

    @property
    def native_value(self) -> int:
        """Количество уроков в расписании на сегодня."""
        st = self._student
        return st.lessons_today_count if st else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Готовый многострочный текст ('text') и расписание уроков на сегодня ('lessons')."""
        st = self._student
        if not st:
            return {}
        return self.coordinator.build_lessons_extra_attributes(st)


class Dnevnik2TurnstileLastSensor(_BaseStudentSensor):
    """Время последнего прохода через турникет школы."""

    _attr_icon = "dnevnik2:turnstile-clock"

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора турникета СКУД."""
        super().__init__(coordinator, entry, education_id, "turnstile_last")

    @property
    def native_value(self) -> str | None:
        """Отметка времени последнего события СКУД."""
        st = self._student
        return st.last_turnstile_event if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Направление и журнал последних событий турникета."""
        st = self._student
        return st.turnstile_attributes if st else {}


class Dnevnik2MealHotBalanceSensor(_BaseStudentSensor):
    """Баланс лицевого счёта столовой (горячего питания) в блоке Диагностика."""

    _attr_icon = "dnevnik2:meal-balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "RUB"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора баланса столовой."""
        super().__init__(coordinator, entry, education_id, "meal_hot_balance")

    @property
    def native_value(self) -> float | None:
        """Остаток средств на счёте столовой (горячего питания)."""
        st = self._student
        return st.meal_hot_balance if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Дополнительные реквизиты счёта столовой."""
        st = self._student
        return st.meal_hot_attributes if st else {}


class Dnevnik2MealBuffetBalanceSensor(_BaseStudentSensor):
    """Баланс лицевого счёта буфета в блоке Диагностика."""

    _attr_icon = "dnevnik2:buffet-balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "RUB"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация сенсора баланса буфета."""
        super().__init__(
            coordinator, entry, education_id, "meal_buffet_balance"
        )

    @property
    def native_value(self) -> float | None:
        """Остаток средств на счёте буфета."""
        st = self._student
        return st.meal_buffet_balance if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Дополнительные реквизиты счёта буфета."""
        st = self._student
        return st.meal_buffet_attributes if st else {}
