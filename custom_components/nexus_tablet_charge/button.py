"""Button: forza la carica fino alla soglia di stop."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_FORCE, tablet_key
from .controller import ChargeController, Tablet
from .entity import TabletEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargeController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ForceChargeButton(controller, t) for t in controller.tablets])


class ForceChargeButton(TabletEntity, ButtonEntity):
    """Carica subito fino alla soglia di stop, poi torna al ciclo normale.

    Serve prima di staccare il tablet dal muro, o quando si sa che seguira'
    un uso intenso: non e' una forzatura permanente, si esaurisce da sola.
    """

    _attr_icon = "mdi:battery-charging-100"

    def __init__(self, controller: ChargeController, tablet: Tablet) -> None:
        super().__init__(controller, tablet_key(tablet.id, KEY_FORCE))
        self._tablet_id = tablet.id
        self._attr_name = f"{tablet.name} carica ora"

    async def async_press(self) -> None:
        await self.controller.async_force_charge(self._tablet_id)
