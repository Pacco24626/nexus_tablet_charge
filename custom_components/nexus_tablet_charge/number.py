"""Number: le due soglie della banda di carica, una coppia per tablet."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, KEY_MAX, KEY_MIN, tablet_key
from .controller import ChargeController, Tablet
from .entity import TabletEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargeController = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = []
    for tablet in controller.tablets:
        entities.append(MinLevelNumber(controller, tablet))
        entities.append(MaxLevelNumber(controller, tablet))
    async_add_entities(entities)


class _SogliaNumber(TabletEntity, NumberEntity):
    """Base delle due soglie: stesso range, stessa persistenza.

    La soglia vive **nelle opzioni della voce**, e non nello stato ripristinato
    dell'entita'. Tenere due verita' - la configurazione e l'ultimo stato - e'
    quello che faceva perdere a ogni riavvio i valori scelti dai cursori.
    """

    _attr_native_min_value = 5
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, controller: ChargeController, tablet: Tablet, key: str) -> None:
        super().__init__(controller, tablet_key(tablet.id, key))
        self._tablet_id = tablet.id
        self._chiave = key

    async def _async_apply(self, value: float, *, riconcilia: bool = True) -> None:
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        await self._async_apply(value)
        await self.controller.async_salva_soglia(self._tablet_id, self._chiave, value)


class MinLevelNumber(_SogliaNumber):
    """Sotto questo livello il caricatore si accende."""

    _attr_icon = "mdi:battery-charging-low"

    def __init__(self, controller: ChargeController, tablet: Tablet) -> None:
        super().__init__(controller, tablet, KEY_MIN)
        self._attr_name = f"{tablet.name} soglia di ricarica"

    @property
    def native_value(self) -> float | None:
        tablet = self.controller.get_tablet(self._tablet_id)
        return tablet.min_level if tablet else None

    async def _async_apply(self, value: float, *, riconcilia: bool = True) -> None:
        await self.controller.async_set_min(self._tablet_id, value, riconcilia=riconcilia)


class MaxLevelNumber(_SogliaNumber):
    """Sopra questo livello il caricatore si spegne."""

    _attr_icon = "mdi:battery-charging-high"

    def __init__(self, controller: ChargeController, tablet: Tablet) -> None:
        super().__init__(controller, tablet, KEY_MAX)
        self._attr_name = f"{tablet.name} soglia di stop"

    @property
    def native_value(self) -> float | None:
        tablet = self.controller.get_tablet(self._tablet_id)
        return tablet.max_level if tablet else None

    async def _async_apply(self, value: float, *, riconcilia: bool = True) -> None:
        await self.controller.async_set_max(self._tablet_id, value, riconcilia=riconcilia)
