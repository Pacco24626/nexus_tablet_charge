"""Config flow: gruppo, tablet in numero libero, parametri di sicurezza."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ADD_ANOTHER,
    CONF_BATTERY_ENTITY,
    CONF_CHARGER_ENTITY,
    CONF_CRITICAL,
    CONF_MAX_LEVEL,
    CONF_MIN_LEVEL,
    CONF_STALE_HOURS,
    CONF_TABLET_ID,
    CONF_TABLET_NAME,
    CONF_TABLETS,
    DEFAULT_CRITICAL,
    DEFAULT_MAX_LEVEL,
    DEFAULT_MIN_LEVEL,
    DEFAULT_STALE_HOURS,
    DOMAIN,
)


def _percentuale(minimo: int, massimo: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimo, max=massimo, step=1, unit_of_measurement="%",
            mode=selector.NumberSelectorMode.SLIDER,
        )
    )


def _tablet_schema(numero: int) -> vol.Schema:
    """Schema di un tablet.

    Il sensore batteria e' quello della companion app; il caricatore puo'
    essere uno switch o una luce, perche' su molti impianti l'uscita e'
    esposta come light.
    """
    return vol.Schema(
        {
            vol.Required(CONF_TABLET_NAME, default=f"Tablet {numero}"): str,
            vol.Required(CONF_BATTERY_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="battery")
            ),
            vol.Required(CONF_CHARGER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "light"])
            ),
            vol.Required(CONF_MIN_LEVEL, default=DEFAULT_MIN_LEVEL): _percentuale(5, 90),
            vol.Required(CONF_MAX_LEVEL, default=DEFAULT_MAX_LEVEL): _percentuale(20, 100),
            vol.Optional(CONF_ADD_ANOTHER, default=False): bool,
        }
    )


def _sicurezza_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_CRITICAL, default=defaults.get(CONF_CRITICAL, DEFAULT_CRITICAL)
            ): _percentuale(1, 30),
            vol.Required(
                CONF_STALE_HOURS,
                default=defaults.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=24, step=1, unit_of_measurement="h",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _valida_soglie(user_input: dict[str, Any]) -> dict[str, str]:
    """La soglia di stop deve stare sopra quella di ricarica."""
    if float(user_input[CONF_MAX_LEVEL]) <= float(user_input[CONF_MIN_LEVEL]):
        return {CONF_MAX_LEVEL: "soglie_incrociate"}
    return {}


class NexusTabletChargeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Creazione di un gruppo di tablet."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._tablets: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._async_abort_entries_match({"name": user_input["name"]})
            self._data["name"] = user_input["name"]
            return await self.async_step_tablet()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("name", default="Tablet"): str}),
        )

    async def async_step_tablet(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Raccoglie un tablet e si richiama finche' l'utente ne aggiunge."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _valida_soglie(user_input)
            if not errors:
                add_another = user_input.pop(CONF_ADD_ANOTHER, False)
                self._tablets.append(
                    {
                        CONF_TABLET_ID: f"tablet_{len(self._tablets) + 1}",
                        CONF_TABLET_NAME: user_input[CONF_TABLET_NAME],
                        CONF_BATTERY_ENTITY: user_input[CONF_BATTERY_ENTITY],
                        CONF_CHARGER_ENTITY: user_input[CONF_CHARGER_ENTITY],
                        CONF_MIN_LEVEL: float(user_input[CONF_MIN_LEVEL]),
                        CONF_MAX_LEVEL: float(user_input[CONF_MAX_LEVEL]),
                    }
                )
                if add_another:
                    return await self.async_step_tablet()
                return await self.async_step_sicurezza()

        return self.async_show_form(
            step_id="tablet",
            data_schema=_tablet_schema(len(self._tablets) + 1),
            description_placeholders={"number": str(len(self._tablets) + 1)},
            errors=errors,
        )

    async def async_step_sicurezza(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._data[CONF_CRITICAL] = float(user_input[CONF_CRITICAL])
            self._data[CONF_STALE_HOURS] = int(user_input[CONF_STALE_HOURS])
            self._data[CONF_TABLETS] = self._tablets
            return self.async_create_entry(title=self._data["name"], data=self._data)

        return self.async_show_form(
            step_id="sicurezza", data_schema=_sicurezza_schema({})
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NexusTabletChargeOptionsFlow()


class NexusTabletChargeOptionsFlow(OptionsFlow):
    """Rimette mano ai tablet e ai parametri di sicurezza."""

    def __init__(self) -> None:
        self._tablets: list[dict[str, Any]] = []

    @property
    def _current(self) -> dict[str, Any]:
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["tablets", "sicurezza"])

    async def async_step_tablets(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Riscrive l'elenco da zero: si ridichiarano tutti i tablet."""
        self._tablets = []
        return await self.async_step_tablet()

    async def async_step_tablet(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _valida_soglie(user_input)
            if not errors:
                add_another = user_input.pop(CONF_ADD_ANOTHER, False)
                self._tablets.append(
                    {
                        CONF_TABLET_ID: f"tablet_{len(self._tablets) + 1}",
                        CONF_TABLET_NAME: user_input[CONF_TABLET_NAME],
                        CONF_BATTERY_ENTITY: user_input[CONF_BATTERY_ENTITY],
                        CONF_CHARGER_ENTITY: user_input[CONF_CHARGER_ENTITY],
                        CONF_MIN_LEVEL: float(user_input[CONF_MIN_LEVEL]),
                        CONF_MAX_LEVEL: float(user_input[CONF_MAX_LEVEL]),
                    }
                )
                if add_another:
                    return await self.async_step_tablet()
                return self._save({CONF_TABLETS: self._tablets})

        indice = len(self._tablets)
        esistenti = self._current.get(CONF_TABLETS, [])
        schema = _tablet_schema(indice + 1)
        if indice < len(esistenti):
            schema = self.add_suggested_values_to_schema(schema, esistenti[indice])

        return self.async_show_form(
            step_id="tablet",
            data_schema=schema,
            description_placeholders={"number": str(indice + 1)},
            errors=errors,
        )

    async def async_step_sicurezza(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._save(
                {
                    CONF_CRITICAL: float(user_input[CONF_CRITICAL]),
                    CONF_STALE_HOURS: int(user_input[CONF_STALE_HOURS]),
                }
            )

        return self.async_show_form(
            step_id="sicurezza", data_schema=_sicurezza_schema(self._current)
        )

    def _save(self, changes: dict[str, Any]) -> ConfigFlowResult:
        """Le opzioni contengono sempre la configurazione completa."""
        merged = {**self._current, **changes}
        merged.pop("name", None)
        return self.async_create_entry(title="", data=merged)
