"""Платформа числовых настроек (number) на основном устройстве аккаунта."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_BALANCE_LIMIT,
    MIN_BALANCE_LIMIT,
    STEP_BALANCE_LIMIT,
)
from .manager import Dnevnik2Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Создаёт числовую настройку лимита баланса питания на основном устройстве."""
    coordinator: Dnevnik2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Dnevnik2BalanceLimitNumber(coordinator, entry)])


class Dnevnik2BalanceLimitNumber(
    CoordinatorEntity[Dnevnik2Coordinator], NumberEntity
):
    """Настраиваемый порог низкого баланса питания (Столовая / Буфет) на основном устройстве."""

    _attr_has_entity_name = True
    _attr_translation_key = "balance_limit"
    _attr_icon = "dnevnik2:meal-balance"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = float(MIN_BALANCE_LIMIT)
    _attr_native_max_value = float(MAX_BALANCE_LIMIT)
    _attr_native_step = float(STEP_BALANCE_LIMIT)
    _attr_native_unit_of_measurement = "RUB"
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: Dnevnik2Coordinator, entry: ConfigEntry
    ) -> None:
        """Инициализация сущности лимита баланса."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_balance_limit"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float:
        """Текущий порог низкого баланса питания в рублях."""
        return float(self.coordinator.balance_limit)

    async def async_set_native_value(self, value: float) -> None:
        """Сохраняет новый порог баланса в настройки интеграции и проверяет текущие балансы."""
        await self.coordinator.async_set_balance_limit(int(round(value)))
