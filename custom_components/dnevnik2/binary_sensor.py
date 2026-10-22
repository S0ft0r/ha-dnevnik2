"""Бинарный сенсор присутствия ученика в школе (по данным турникета СКУД)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .manager import Dnevnik2Coordinator, StudentData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт бинарный сенсор присутствия в школе для каждого ученика."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        Dnevnik2AtSchoolBinarySensor(coordinator, entry, edu_id)
        for edu_id in coordinator.students
    )


class Dnevnik2AtSchoolBinarySensor(
    CoordinatorEntity[Dnevnik2Coordinator], BinarySensorEntity
):
    """Бинарный сенсор 'В школе' на подустройстве ученика."""

    _attr_has_entity_name = True
    _attr_translation_key = "at_school"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    @property
    def icon(self) -> str:
        """Динамическая иконка присутствия в школе."""
        return "mdi:school" if self.is_on else "dnevnik2:school-off"

    def __init__(
        self,
        coordinator: Dnevnik2Coordinator,
        entry: ConfigEntry,
        education_id: str,
    ) -> None:
        """Инициализация бинарного сенсора турникета."""
        super().__init__(coordinator)
        self._edu_id = education_id
        self._attr_unique_id = (
            f"{entry.entry_id}_student_{education_id}_at_school"
        )
        student = coordinator.students.get(education_id)
        if student is not None:
            self._attr_device_info = DeviceInfo(
                **coordinator.device_info_for_student(student)
            )

    @property
    def _student(self) -> StudentData | None:
        return self.coordinator.students.get(self._edu_id)

    @property
    def is_on(self) -> bool | None:
        """Возвращает True, если последнее событие турникета — вход в школу."""
        st = self._student
        return st.at_school if st else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Время и направление последнего прохода."""
        st = self._student
        if not st:
            return {}
        return {
            "last_event": st.last_turnstile_event,
            **st.turnstile_attributes,
        }
