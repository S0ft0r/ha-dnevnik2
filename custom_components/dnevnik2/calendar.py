"""Платформа календаря (Platform.CALENDAR) для расписания уроков каждого учащегося."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .manager import SPB_TZ, Dnevnik2Coordinator, LessonTask, StudentData


def _parse_hhmm_time(raw_hhmm: str) -> time | None:
    """Преобразует строку 'HH:MM' в объект datetime.time."""
    parts = raw_hhmm.strip().split(":")
    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        hh = int(parts[0])
        mm = int(parts[1])
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hh, mm)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт сущность календаря уроков на подустройстве каждого учащегося (если включено в настройках)."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.enable_calendar:
        return

    entities: list[CalendarEntity] = [
        Dnevnik2StudentScheduleCalendar(coordinator, entry, edu_id)
        for edu_id in coordinator.known_students
    ]
    if entities:
        async_add_entities(entities)


class Dnevnik2StudentScheduleCalendar(
    CoordinatorEntity[Dnevnik2Coordinator], CalendarEntity
):
    """Календарь расписания уроков учащегося с кабинетом, учителем и ДЗ."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule"
    _attr_icon = "dnevnik2:schedule"

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация календаря расписания уроков."""
        super().__init__(coordinator)
        self._entry = entry
        self._edu_id = education_id
        self._attr_unique_id = (
            f"{entry.entry_id}_student_{education_id}_schedule"
        )
        student = coordinator.known_students.get(education_id)
        if student is not None:
            self._attr_device_info = DeviceInfo(
                **coordinator.device_info_for_student(student)
            )

    @property
    def _student(self) -> StudentData | None:
        return self.coordinator.students.get(self._edu_id)

    def _lesson_to_event(self, lesson: LessonTask) -> CalendarEvent:
        """Преобразует урок расписания в событие календаря Home Assistant."""
        t_start = _parse_hhmm_time(lesson.time_from)
        t_end = _parse_hhmm_time(lesson.time_to)
        num_int = int(lesson.number) if lesson.number.isdigit() else 1
        num_int = max(1, min(12, num_int))

        if t_start is not None:
            start_dt = datetime.combine(lesson.due, t_start, tzinfo=SPB_TZ)
        else:
            base_dt = datetime.combine(
                lesson.due, time(8, 30), tzinfo=SPB_TZ
            )
            start_dt = base_dt + timedelta(minutes=(num_int - 1) * 55)

        if t_end is not None:
            end_dt = datetime.combine(lesson.due, t_end, tzinfo=SPB_TZ)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(minutes=45)
        else:
            end_dt = start_dt + timedelta(minutes=45)

        summary = (
            f"{lesson.number}. {lesson.subject}"
            if lesson.number
            else lesson.subject
        )
        room_lbl = self.coordinator.tr_common("room_short")
        location = f"{room_lbl} {lesson.room}" if lesson.room else None

        desc_lines: list[str] = []
        if lesson.teacher:
            teacher_lbl = self.coordinator.tr_common("teacher_prefix")
            desc_lines.append(f"{teacher_lbl}: {lesson.teacher}")
        if lesson.homework_text:
            hw_lbl = self.coordinator.tr_common("homework_prefix")
            desc_lines.append(f"{hw_lbl}: {lesson.homework_text}")
        description = "\n".join(desc_lines) if desc_lines else None

        return CalendarEvent(
            start=start_dt,
            end=end_dt,
            summary=summary,
            description=description,
            location=location,
            uid=lesson.uid,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Текущий или ближайший следующий урок учащегося."""
        st = self._student
        if not st or not st.calendar_lessons:
            return None
        now = datetime.now(SPB_TZ)
        for lesson in st.calendar_lessons:
            if lesson.due < now.date():
                continue
            ev = self._lesson_to_event(lesson)
            if ev.end > now:
                return ev
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Возвращает список уроков за запрошенный в календаре диапазон дат."""
        d_start = start_date.astimezone(SPB_TZ).date()
        d_end = end_date.astimezone(SPB_TZ).date()
        lessons = await self.coordinator.async_get_calendar_lessons(
            self._edu_id, d_start, d_end
        )
        events: list[CalendarEvent] = []
        for lesson in lessons:
            ev = self._lesson_to_event(lesson)
            if ev.end > start_date and ev.start < end_date:
                events.append(ev)
        return events
