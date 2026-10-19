"""Integrazione Nexus Tablet Charge: ciclo di carica dei tablet a muro.

La scheda la serve e la registra l'integrazione: nessuna risorsa da aggiungere
a mano, e l'URL porta la versione, cosi' dopo un aggiornamento il browser
ricarica il file invece di usare quello in cache.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import CARD_FILE, CARD_URL_BASE, DOMAIN, PLATFORMS
from .controller import ChargeController

_LOGGER = logging.getLogger(__name__)

# La risorsa si riconosce dal percorso completo. Dal solo nome del file si
# prenderebbe anche quella della vecchia scheda separata, che HACS serve da
# /hacsfiles/nexus_tablet_charge_card/ con lo stesso nome: riscriverla
# significherebbe mettere le mani su una risorsa di qualcun altro.
CARD_PATH = f"{CARD_URL_BASE}/{CARD_FILE}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura un gruppo di tablet."""
    try:
        await _async_registra_card(hass)
    except Exception as err:  # noqa: BLE001
        # La scheda e' una vetrina: se non si registra, la carica deve
        # funzionare lo stesso.
        _LOGGER.warning("Scheda non registrata (%s): la carica funziona comunque", err)

    controller = ChargeController(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await controller.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Scarica il gruppo e stacca gli osservatori."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        controller: ChargeController = hass.data[DOMAIN].pop(entry.entry_id)
        await controller.async_shutdown()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricarica dopo una modifica dalle opzioni."""
    await hass.config_entries.async_reload(entry.entry_id)


# -----------------------------------------------------------------------------
# Scheda Lovelace
# -----------------------------------------------------------------------------
def _percorso(risorsa: dict) -> str:
    """Il percorso dell'URL di una risorsa, senza la versione in coda."""
    return urlsplit(risorsa.get("url") or "").path


async def _async_registra_card(hass: HomeAssistant) -> None:
    """Serve la scheda e la registra come risorsa, una volta sola per avvio."""
    dominio = hass.data.setdefault(DOMAIN, {})
    if dominio.get("card_registrata"):
        return

    www = os.path.join(os.path.dirname(__file__), "www")
    if not await hass.async_add_executor_job(os.path.isdir, www):
        _LOGGER.warning("Cartella www assente: la scheda non verra' servita")
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, www, False)]
        )
    except RuntimeError as err:
        _LOGGER.debug("Percorso statico gia' registrato: %s", err)

    integrazione = await async_get_integration(hass, DOMAIN)
    url = f"{CARD_PATH}?v={integrazione.version}"

    if hass.is_running:
        await _async_registra_risorsa(hass, url)
    else:
        # Scrivere nelle risorse Lovelace mentre Home Assistant sta avviando
        # significa toccare lo storage in una fase gia' affollata.
        async def _dopo_avvio(_event) -> None:
            await _async_registra_risorsa(hass, url)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _dopo_avvio)

    dominio["card_registrata"] = True


async def _async_registra_risorsa(hass: HomeAssistant, url: str) -> None:
    """Registra la scheda come risorsa Lovelace.

    E' l'unico meccanismo che Lovelace attende prima di disegnare: con il solo
    add_extra_js_url la plancia puo' disegnare prima che l'elemento sia
    definito e mostrare «Custom element doesn't exist». Il ripiego resta per
    chi ha Lovelace in modalita' YAML, dove le risorse non si scrivono da
    codice.
    """
    lovelace = hass.data.get("lovelace")
    risorse = getattr(lovelace, "resources", None)
    if risorse is None and isinstance(lovelace, dict):
        risorse = lovelace.get("resources")
    if risorse is None:
        add_extra_js_url(hass, url)
        return

    try:
        await risorse.async_get_info()
        voci = list(risorse.async_items())
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Impossibile leggere le risorse Lovelace (%s). Aggiungi a mano la "
            "scheda come modulo JavaScript: %s",
            err,
            url,
        )
        add_extra_js_url(hass, url)
        return

    esistente = next((r for r in voci if _percorso(r) == CARD_PATH), None)

    # Chi aveva la vecchia scheda come plugin HACS se la ritrova registrata
    # due volte: lo stesso elemento definito da due file, e vince chi arriva
    # prima. Non la tocchiamo - non e' nostra - ma lo diciamo.
    altrove = [
        r.get("url")
        for r in voci
        if _percorso(r) != CARD_PATH and _percorso(r).endswith(f"/{CARD_FILE}")
    ]
    if altrove:
        _LOGGER.warning(
            "Un'altra risorsa Lovelace serve lo stesso file (%s): dalla 1.1.0 la "
            "scheda e' dentro l'integrazione. Disinstalla la vecchia scheda da HACS "
            "e togli quella risorsa, altrimenti il file viene caricato due volte.",
            ", ".join(a for a in altrove if a),
        )

    if not hasattr(risorse, "async_create_item"):
        # Lovelace in modalita' YAML: le risorse le scrive l'utente.
        if esistente is None:
            add_extra_js_url(hass, url)
            _LOGGER.info(
                "Lovelace in modalita' YAML: scheda caricata come modulo extra (%s)", url
            )
        elif esistente.get("url") != url:
            _LOGGER.info(
                "Lovelace in modalita' YAML: la risorsa della scheda e' %s, aggiornala a %s",
                esistente.get("url"),
                url,
            )
        return

    try:
        if esistente is None:
            await risorse.async_create_item({"res_type": "module", "url": url})
            _LOGGER.info("Risorsa Lovelace della scheda creata: %s", url)
        elif esistente.get("url") != url:
            await risorse.async_update_item(esistente["id"], {"url": url})
            _LOGGER.info("Risorsa Lovelace della scheda aggiornata: %s", url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Impossibile registrare la risorsa Lovelace (%s). Aggiungila a mano "
            "come modulo JavaScript: %s",
            err,
            url,
        )
        add_extra_js_url(hass, url)
