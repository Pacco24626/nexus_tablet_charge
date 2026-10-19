"""Number: le due soglie della banda di carica, una coppia per tablet."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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


class _SogliaNumber(TabletEntity, NumberEntity, RestoreEntity):
    """Base delle due soglie: stesso range, stessa persistenza."""

    _attr_native_min_value = 5
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, controller: ChargeController, tablet: Tablet, key: str) -> None:
        super().__init__(controller, tablet_key(tablet.id, key))
        self._tablet_id = tablet.id
        self._chiave = key

    def _dalla_configurazione(self) -> bool:
        """Vero se questa soglia e' scritta nelle opzioni della voce."""
        tablet = self.controller.get_tablet(self._tablet_id)
        if tablet is None:
            return False
        return tablet.min_configurato if self._chiave == KEY_MIN else tablet.max_configurato

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._dalla_configurazione():
            # La soglia la decide la configurazione. Senza questo, salvare le
            # opzioni ricaricava la voce e il vecchio stato ripristinato si
            # rimetteva al posto del valore appena scelto dall'utente.
            return
        last = await self.async_get_last_state()
        if last is None:
            return
        try:
            # Si applica il valore, ma senza riconciliare: vedi il commento in
            # controller.async_set_min.
            await self._async_apply(float(last.state), riconcilia=False)
        except (TypeError, ValueError):
            pass

    async def _async_apply(self, value: float, *, riconcilia: bool = True) -> None:
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        await self._async_apply(value)


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
