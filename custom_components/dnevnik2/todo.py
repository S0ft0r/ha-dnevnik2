"""Платформа списков дел (Platform.TODO) для домашних заданий и уроков каждого ученика."""

from __future__ import annotations

from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OUTPUT_MODE_TODO
from .manager import Dnevnik2Coordinator, StudentData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт списки Todo (ДЗ и/или уроки) на подустройстве каждого ученика согласно выбранным настройкам."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TodoListEntity] = []
    hw_as_todo = coordinator.homework_mode == OUTPUT_MODE_TODO
    lessons_as_todo = coordinator.lessons_mode == OUTPUT_MODE_TODO

    for edu_id in coordinator.students:
        if hw_as_todo:
            entities.append(
                Dnevnik2StudentHomeworkTodo(coordinator, entry, edu_id)
            )
        if lessons_as_todo:
            entities.append(
                Dnevnik2StudentLessonsTodo(coordinator, entry, edu_id)
            )

    if entities:
        async_add_entities(entities)


class _BaseStudentTodo(
    CoordinatorEntity[Dnevnik2Coordinator], TodoListEntity
):
    """Базовый класс списка Todo на подустройстве ученика."""

    _attr_has_entity_name = True
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
        key: str,
    ) -> None:
        """Привязывает список Todo к подустройству конкретного ученика."""
        super().__init__(coordinator)
        self._entry = entry
        self._edu_id = education_id
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_student_{education_id}_{key}"
        student = coordinator.students.get(education_id)
        if student is not None:
            self._attr_device_info = DeviceInfo(
                **coordinator.device_info_for_student(student)
            )

    @property
    def _student(self) -> StudentData | None:
        return self.coordinator.students.get(self._edu_id)

    def _todo_friendly_name(self) -> str | None:
        """Формирует friendly_name вида 'Александр - домашние задания' для панели 'Списки дел'."""
        st = self._student
        orig = self.name
        if st and isinstance(orig, str) and orig:
            lowered = orig[0].lower() + orig[1:]
            return f"{st.first_name} - {lowered}"
        return orig if isinstance(orig, str) else None

    def _friendly_name_internal(self) -> str | None:
        """Возвращает кастомный friendly_name с дефисом для панели 'Списки дел'."""
        return self._todo_friendly_name()

    @callback
    def _async_write_ha_state(self) -> None:
        """Сохраняет original_name ('Домашние задания') для карточки устройства, а в friendly_name пишет 'Имя - домашние задания'."""
        orig = self.name
        if isinstance(orig, str) and orig:
            self._cached_friendly_name = (orig, self._todo_friendly_name())
        super()._async_write_ha_state()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Сохраняет отметку выполнения элемента в Home Assistant."""
        if not item.uid:
            return
        is_completed = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.async_set_item_completed(item.uid, is_completed)


class Dnevnik2StudentHomeworkTodo(_BaseStudentTodo):
    """Список домашних заданий ученика на сегодня и ближайшие дни."""

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация списка Todo домашних заданий."""
        super().__init__(coordinator, entry, education_id, "homework")

    @property
    def icon(self) -> str:
        """Динамическая иконка: книга с карандашом (есть невыполненные ДЗ) или с галочкой (всё выполнено)."""
        st = self._student
        if not st:
            return "dnevnik2:homework-done"
        has_uncompleted = any(
            not self.coordinator.is_item_completed(task.uid)
            for task in st.homework_tasks
        )
        return "dnevnik2:homework" if has_uncompleted else "dnevnik2:homework-done"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Актуальные домашние задания ученика с датой сдачи и отметкой выполнения."""
        st = self._student
        if not st:
            return []
        return [
            TodoItem(
                uid=task.uid,
                summary=f"{task.subject}: {task.task}",
                due=task.due,
                status=(
                    TodoItemStatus.COMPLETED
                    if self.coordinator.is_item_completed(task.uid)
                    else TodoItemStatus.NEEDS_ACTION
                ),
            )
            for task in st.homework_tasks
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Готовый текстовый атрибут невыполненных и всех заданий для автоматизаций и Blueprint."""
        st = self._student
        if not st:
            return {}
        return self.coordinator.build_homework_extra_attributes(st)


class Dnevnik2StudentLessonsTodo(_BaseStudentTodo):
    """Список уроков расписания ученика на сегодня в формате Todo."""

    _attr_icon = "dnevnik2:schedule"

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация списка Todo расписания уроков."""
        super().__init__(coordinator, entry, education_id, "lessons_today")

    @property
    def todo_items(self) -> list[TodoItem] | None:
        """Уроки на сегодня с временем, кабинетом и преподавателем."""
        st = self._student
        if not st:
            return []
        room_lbl = self.coordinator.tr_common("room_short")
        return [
            TodoItem(
                uid=lesson.uid,
                summary=f"{lesson.number}. {lesson.time_from}–{lesson.time_to} {lesson.subject}",
                description=f"{room_lbl} {lesson.room} • {lesson.teacher}",
                due=lesson.due,
                status=(
                    TodoItemStatus.COMPLETED
                    if self.coordinator.is_item_completed(lesson.uid)
                    else TodoItemStatus.NEEDS_ACTION
                ),
            )
            for lesson in st.lesson_tasks
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Готовый текстовый атрибут расписания уроков для автоматизаций и Blueprint."""
        st = self._student
        if not st:
            return {}
        return self.coordinator.build_lessons_extra_attributes(st)
