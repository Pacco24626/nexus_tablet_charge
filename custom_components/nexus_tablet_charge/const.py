"""Costanti dell'integrazione Nexus Tablet Charge."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "nexus_tablet_charge"
MANUFACTURER = "Nexus-T"
MODEL = "Gestione carica tablet"

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# --- Chiavi di configurazione -------------------------------------------------
CONF_TABLETS = "tablets"
CONF_TABLET_ID = "id"
CONF_TABLET_NAME = "name"
CONF_BATTERY_ENTITY = "battery_entity"
CONF_CHARGER_ENTITY = "charger_entity"
CONF_MIN_LEVEL = "min_level"
CONF_MAX_LEVEL = "max_level"
CONF_ADD_ANOTHER = "add_another"

CONF_CRITICAL = "critical"
CONF_STALE_HOURS = "stale_hours"

# --- Stati per tablet ---------------------------------------------------------
STATUS_CHARGING = "charging"
STATUS_DISCHARGING = "discharging"
STATUS_CRITICAL = "critical"
STATUS_FORCED = "forced"
STATUS_FAILSAFE = "failsafe"
STATUS_DISABLED = "disabled"
STATUS_OPTIONS = [
    STATUS_CHARGING,
    STATUS_DISCHARGING,
    STATUS_CRITICAL,
    STATUS_FORCED,
    STATUS_FAILSAFE,
    STATUS_DISABLED,
]

# --- Stato del gruppo ---------------------------------------------------------
GROUP_OK = "ok"
GROUP_FAILSAFE = "failsafe"
GROUP_OPTIONS = [GROUP_OK, GROUP_FAILSAFE]

# --- Chiavi delle entita' -----------------------------------------------------
KEY_GROUP_STATUS = "group_status"


def tablet_key(tablet_id: str, suffix: str) -> str:
    """Chiave univoca di un'entita' legata a un tablet."""
    return f"{tablet_id}_{suffix}"


KEY_MIN = "min_level"
KEY_MAX = "max_level"
KEY_ENABLE = "enable"
KEY_FORCE = "force"
KEY_STATUS = "status"

# --- Parametri operativi ------------------------------------------------------
# Riconciliazione periodica: copre il sensore che si blocca senza diventare
# unavailable e qualunque comando manuale sull'uscita del caricatore.
RECONCILE_INTERVAL = 300

DEFAULT_MIN_LEVEL = 40
DEFAULT_MAX_LEVEL = 80
DEFAULT_CRITICAL = 15
DEFAULT_STALE_HOURS = 3

# --- Scheda Lovelace ----------------------------------------------------------
# Servita dall'integrazione: nessuna risorsa da aggiungere a mano.
CARD_URL_BASE = "/nexus_tablet_charge"
CARD_FILE = "nexus-tablet-charge-card.js"
