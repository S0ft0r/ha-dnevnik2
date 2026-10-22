"""Кнопка принудительного обновления данных дневника на основном устройстве."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .manager import Dnevnik2Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт кнопку обновления данных на основном устройстве."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Dnevnik2RefreshButton(coordinator, entry)])


class Dnevnik2RefreshButton(
    CoordinatorEntity[Dnevnik2Coordinator], ButtonEntity
):
    """Кнопка внеочередного опроса API дневника."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:database-sync"

    def __init__(
        self, coordinator: Dnevnik2Coordinator, entry: ConfigEntry
    ) -> None:
        """Инициализация кнопки обновления."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Запускает немедленное обновление координатора."""
        await self.coordinator.async_request_refresh()
