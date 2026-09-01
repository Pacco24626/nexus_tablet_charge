"""Classe base delle entita' del gruppo tablet."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .controller import ChargeController


class TabletEntity(Entity):
    """Entita' agganciata al controller del gruppo."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: ChargeController, key: str) -> None:
        self.controller = controller
        self._key = key
        self._attr_unique_id = f"{controller.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.entry.entry_id)},
            name=controller.name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))
