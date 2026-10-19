"""Controller: decide se ogni caricatore deve stare acceso o spento.

La logica e' la stessa del blueprint da cui nasce questa integrazione, con una
regola sola: la funzione che calcola lo stato desiderato e' pura e idempotente.
Qualunque evento — batteria cambiata, riconciliazione periodica, avvio di Home
Assistant, comando manuale — porta allo stesso calcolo, quindi non esistono
stati incoerenti da rimettere a posto.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
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
    GROUP_FAILSAFE,
    GROUP_OK,
    RECONCILE_INTERVAL,
    STATUS_CHARGING,
    STATUS_CRITICAL,
    STATUS_DISABLED,
    STATUS_DISCHARGING,
    STATUS_FAILSAFE,
    STATUS_FORCED,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Tablet:
    """Un tablet gestito, con i suoi parametri e il suo stato."""

    id: str
    name: str
    battery_entity: str
    charger_entity: str
    min_level: float
    max_level: float
    # Vero se la soglia e' scritta nella configurazione: in quel caso vince
    # lei, e lo stato ripristinato all'avvio non la tocca.
    min_configurato: bool = False
    max_configurato: bool = False

    # --- runtime ---
    enabled: bool = True
    force: bool = False
    status: str = STATUS_DISCHARGING
    level: float = field(default=-1.0)
    stale: bool = False


class ChargeController:
    """Gestisce la carica di tutti i tablet di una config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        cfg = {**entry.data, **entry.options}
        self.name: str = cfg.get("name", "Tablet")
        self.tablets: list[Tablet] = [
            Tablet(
                id=t[CONF_TABLET_ID],
                name=t[CONF_TABLET_NAME],
                battery_entity=t[CONF_BATTERY_ENTITY],
                charger_entity=t[CONF_CHARGER_ENTITY],
                min_level=float(t.get(CONF_MIN_LEVEL, DEFAULT_MIN_LEVEL)),
                max_level=float(t.get(CONF_MAX_LEVEL, DEFAULT_MAX_LEVEL)),
                min_configurato=CONF_MIN_LEVEL in t,
                max_configurato=CONF_MAX_LEVEL in t,
            )
            for t in cfg.get(CONF_TABLETS, [])
        ]
        self.critical: float = float(cfg.get(CONF_CRITICAL, DEFAULT_CRITICAL))
        self.stale_hours: int = int(cfg.get(CONF_STALE_HOURS, DEFAULT_STALE_HOURS))

        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []

    # -------------------------------------------------------------------------
    # Ciclo di vita
    # -------------------------------------------------------------------------
    async def async_setup(self) -> None:
        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [t.battery_entity for t in self.tablets],
                self._async_battery_changed,
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._async_periodic,
                timedelta(seconds=RECONCILE_INTERVAL),
            )
        )

        if self.hass.is_running:
            await self.async_reconcile()
        else:
            # A boot in corso i sensori della companion app non hanno ancora
            # riportato nulla: agire adesso vorrebbe dire leggere unknown e
            # far scattare il fail-safe su tutti i tablet.
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self._async_on_started
            )

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def _async_on_started(self, _event: Event) -> None:
        await self.async_reconcile()

    async def _async_battery_changed(self, _event: Event) -> None:
        await self.async_reconcile()

    async def _async_periodic(self, _now: datetime) -> None:
        await self.async_reconcile()

    @callback
    def async_add_listener(self, update: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def _remove() -> None:
            self._listeners.remove(update)

        return _remove

    @callback
    def notify(self) -> None:
        for update in list(self._listeners):
            update()

    # -------------------------------------------------------------------------
    # Parametri pilotati dalle entita'
    # -------------------------------------------------------------------------
    def get_tablet(self, tablet_id: str) -> Tablet | None:
        return next((t for t in self.tablets if t.id == tablet_id), None)

    # `riconcilia=False` serve al ripristino degli stati all'avvio: li' il
    # valore va messo nel tablet, ma agire sui caricatori no. A boot in corso
    # i sensori della companion app sono ancora sconosciuti e la
    # riconciliazione scavalcherebbe la guardia di async_setup, mandando ogni
    # tablet in sicurezza: caricatore acceso e notifica «non risponde» a ogni
    # riavvio. La prima riconciliazione la fa l'evento di avvio.
    async def async_set_min(
        self, tablet_id: str, value: float, *, riconcilia: bool = True
    ) -> None:
        if (tablet := self.get_tablet(tablet_id)) is not None:
            tablet.min_level = value
            if riconcilia:
                await self.async_reconcile()

    async def async_set_max(
        self, tablet_id: str, value: float, *, riconcilia: bool = True
    ) -> None:
        if (tablet := self.get_tablet(tablet_id)) is not None:
            tablet.max_level = value
            if riconcilia:
                await self.async_reconcile()

    async def async_set_enabled(
        self, tablet_id: str, value: bool, *, riconcilia: bool = True
    ) -> None:
        if (tablet := self.get_tablet(tablet_id)) is not None:
            tablet.enabled = value
            if not value:
                tablet.force = False
            if riconcilia:
                await self.async_reconcile()

    async def async_force_charge(self, tablet_id: str) -> None:
        """Carica fino alla soglia di stop, poi torna al ciclo normale."""
        if (tablet := self.get_tablet(tablet_id)) is not None:
            tablet.force = True
            await self.async_reconcile()

    # -------------------------------------------------------------------------
    # Riconciliazione
    # -------------------------------------------------------------------------
    async def async_reconcile(self) -> None:
        for tablet in self.tablets:
            desired, status = self._evaluate(tablet)
            tablet.status = status

            if desired is None:
                continue
            if self.charger_is_on(tablet) == desired:
                # Nessun comando inutile: ogni scatto e' usura del rele'
                # dell'attuatore.
                continue
            await self._async_set_charger(tablet, desired)

        self._sync_notifications()
        self.notify()

    def _evaluate(self, tablet: Tablet) -> tuple[bool | None, str]:
        """Stato desiderato del caricatore e stato dichiarato del tablet.

        Restituisce None quando il caricatore non va toccato.
        """
        if not tablet.enabled:
            return None, STATUS_DISABLED

        level, stale = self._read_battery(tablet)
        tablet.level = level
        tablet.stale = stale

        # Fail-safe: senza un dato attendibile si carica. Il modo peggiore di
        # sbagliare e' lasciare il caricatore spento non sapendo a che punto e'
        # la batteria: il tablet muore e il pannello a muro resta nero.
        if level < 0 or stale:
            return True, STATUS_FAILSAFE

        if level <= self.critical:
            return True, STATUS_CRITICAL

        if tablet.force:
            if level >= tablet.max_level:
                tablet.force = False
            else:
                return True, STATUS_FORCED

        if level <= tablet.min_level:
            return True, STATUS_CHARGING
        if level >= tablet.max_level:
            return False, STATUS_DISCHARGING

        # Banda morta fra le due soglie: si mantiene lo stato attuale. E' cio'
        # che impedisce al rele' di ticchettare sul valore di soglia.
        acceso = self.charger_is_on(tablet)
        return acceso, STATUS_CHARGING if acceso else STATUS_DISCHARGING

    def _read_battery(self, tablet: Tablet) -> tuple[float, bool]:
        """Livello e anzianita' del dato. Livello -1 se non leggibile."""
        state = self.hass.states.get(tablet.battery_entity)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return -1.0, False

        try:
            level = float(state.state)
        except (TypeError, ValueError):
            return -1.0, False

        # last_reported cambia a ogni invio anche quando il valore e' identico;
        # last_updated e' il ripiego sulle versioni che non lo espongono.
        ultimo = getattr(state, "last_reported", None) or state.last_updated
        stale = (dt_util.utcnow() - ultimo).total_seconds() > self.stale_hours * 3600
        return level, stale

    def charger_is_on(self, tablet: Tablet) -> bool:
        state = self.hass.states.get(tablet.charger_entity)
        return state is not None and state.state == "on"

    async def _async_set_charger(self, tablet: Tablet, turn_on: bool) -> None:
        service = "turn_on" if turn_on else "turn_off"
        try:
            await self.hass.services.async_call(
                "homeassistant",
                service,
                {"entity_id": tablet.charger_entity},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.error(
                "%s: comando %s su %s fallito: %s",
                tablet.name,
                service,
                tablet.charger_entity,
                err,
            )

    # -------------------------------------------------------------------------
    # Notifiche
    # -------------------------------------------------------------------------
    def _sync_notifications(self) -> None:
        """Una notifica per tablet in fail-safe, ritirata quando rientra."""
        for tablet in self.tablets:
            notification_id = f"{DOMAIN}_{self.entry.entry_id}_{tablet.id}"
            if tablet.status == STATUS_FAILSAFE:
                persistent_notification.async_create(
                    self.hass,
                    f"{tablet.name} non riporta il livello di batteria da piu' "
                    f"di {self.stale_hours} ore. Il caricatore e' stato acceso "
                    f"in via precauzionale: controlla che la companion app sia "
                    f"attiva sul dispositivo.",
                    title="Carica tablet: fail-safe",
                    notification_id=notification_id,
                )
            else:
                persistent_notification.async_dismiss(self.hass, notification_id)

    # -------------------------------------------------------------------------
    # Stato del gruppo
    # -------------------------------------------------------------------------
    @property
    def group_status(self) -> str:
        if any(t.status == STATUS_FAILSAFE for t in self.tablets):
            return GROUP_FAILSAFE
        return GROUP_OK
