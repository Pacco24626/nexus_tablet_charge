"""Switch: abilitazione della gestione, uno per tablet."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, KEY_ENABLE, tablet_key
from .controller import ChargeController, Tablet
from .entity import TabletEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargeController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ManagementSwitch(controller, tablet) for tablet in controller.tablets]
    )


class ManagementSwitch(TabletEntity, SwitchEntity, RestoreEntity):
    """Abilita il ciclo di carica per questo tablet.

    Spento, l'integrazione smette di comandare il caricatore e lo lascia
    com'e': serve per la manutenzione, o per un tablet staccato dal muro.
    """

    _attr_icon = "mdi:battery-heart-variant"
    # Governa un comportamento, non e' un dispositivo da accendere: con la
    # categoria «config» Home Assistant non lo espone agli assistenti vocali,
    # dove un comando generico se lo porterebbe via insieme alle lampade.
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, controller: ChargeController, tablet: Tablet) -> None:
        super().__init__(controller, tablet_key(tablet.id, KEY_ENABLE))
        self._tablet_id = tablet.id
        self._attr_name = f"{tablet.name} gestione carica"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            # Senza riconciliare: a boot in corso i sensori della companion sono
            # sconosciuti e ogni tablet finirebbe in sicurezza. Vedi il commento
            # in controller.async_set_enabled.
            await self.controller.async_set_enabled(
                self._tablet_id, last.state == "on", riconcilia=False
            )

    @property
    def is_on(self) -> bool:
        tablet = self.controller.get_tablet(self._tablet_id)
        return tablet.enabled if tablet else False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tablet = self.controller.get_tablet(self._tablet_id)
        if tablet is None:
            return {}
        return {
            "battery_entity": tablet.battery_entity,
            "charger_entity": tablet.charger_entity,
            "level": tablet.level if tablet.level >= 0 else None,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set_enabled(self._tablet_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set_enabled(self._tablet_id, False)
