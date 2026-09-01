"""Sensori: stato per tablet, piu' il sensore di gruppo che alimenta la card.

Il sensore di gruppo porta negli attributi la mappa completa: tablet, entita'
delle soglie, pulsanti, livelli. La card si configura sapendo solo il suo
entity_id, e un tablet aggiunto dall'integrazione compare da solo.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    GROUP_OPTIONS,
    KEY_ENABLE,
    KEY_FORCE,
    KEY_GROUP_STATUS,
    KEY_MAX,
    KEY_MIN,
    KEY_STATUS,
    STATUS_OPTIONS,
    tablet_key,
)
from .controller import ChargeController, Tablet
from .entity import TabletEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargeController = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [GroupStatusSensor(controller)]
    entities += [TabletStatusSensor(controller, t) for t in controller.tablets]
    async_add_entities(entities)


class TabletStatusSensor(TabletEntity, SensorEntity):
    """Che cosa sta facendo il ciclo su questo tablet."""

    _attr_icon = "mdi:tablet-dashboard"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUS_OPTIONS
    _attr_translation_key = "tablet_status"

    def __init__(self, controller: ChargeController, tablet: Tablet) -> None:
        super().__init__(controller, tablet_key(tablet.id, KEY_STATUS))
        self._tablet_id = tablet.id
        self._attr_name = f"{tablet.name} stato"

    @property
    def native_value(self) -> str | None:
        tablet = self.controller.get_tablet(self._tablet_id)
        return tablet.status if tablet else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        tablet = self.controller.get_tablet(self._tablet_id)
        if tablet is None:
            return {}
        return {
            "level": tablet.level if tablet.level >= 0 else None,
            "min_level": tablet.min_level,
            "max_level": tablet.max_level,
            "forced": tablet.force,
            "stale": tablet.stale,
        }


class GroupStatusSensor(TabletEntity, SensorEntity):
    """Stato complessivo del gruppo, con la mappa delle entita' per la card."""

    _attr_name = "Stato"
    _attr_icon = "mdi:tablet-cellphone"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = GROUP_OPTIONS
    _attr_translation_key = "group_status"

    def __init__(self, controller: ChargeController) -> None:
        super().__init__(controller, KEY_GROUP_STATUS)

    @property
    def native_value(self) -> str:
        return self.controller.group_status

    def _entity_id(self, platform: str, key: str) -> str | None:
        return er.async_get(self.hass).async_get_entity_id(
            platform, DOMAIN, f"{self.controller.entry.entry_id}_{key}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        controller = self.controller
        tablets = []
        for tablet in controller.tablets:
            tablets.append(
                {
                    "id": tablet.id,
                    "name": tablet.name,
                    "battery_entity": tablet.battery_entity,
                    "charger_entity": tablet.charger_entity,
                    "level": tablet.level if tablet.level >= 0 else None,
                    "min_level": tablet.min_level,
                    "max_level": tablet.max_level,
                    "status": tablet.status,
                    "charging": controller.charger_is_on(tablet),
                    "min_entity": self._entity_id("number", tablet_key(tablet.id, KEY_MIN)),
                    "max_entity": self._entity_id("number", tablet_key(tablet.id, KEY_MAX)),
                    "enable_entity": self._entity_id(
                        "switch", tablet_key(tablet.id, KEY_ENABLE)
                    ),
                    "force_button": self._entity_id(
                        "button", tablet_key(tablet.id, KEY_FORCE)
                    ),
                    "status_entity": self._entity_id(
                        "sensor", tablet_key(tablet.id, KEY_STATUS)
                    ),
                }
            )

        return {
            "group": controller.name,
            "tablets": tablets,
            "critical": controller.critical,
            "stale_hours": controller.stale_hours,
        }
