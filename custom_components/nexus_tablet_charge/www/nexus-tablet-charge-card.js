/**
 * Nexus Tablet Charge Card
 *
 * Card grafica per l'integrazione nexus_tablet_charge.
 *
 * Si configura con un solo entity_id: quello del sensore di stato del gruppo.
 * Tablet, soglie, pulsanti e livelli vengono letti dai suoi attributi, quindi
 * un tablet aggiunto dall'integrazione compare da solo senza toccare la
 * configurazione della dashboard.
 */

const CARD_VERSION = "1.0.2";

console.info(
  `%c NEXUS-TABLET-CHARGE-CARD %c ${CARD_VERSION} `,
  "color: white; background: #5f3dc4; font-weight: 700;",
  "color: #5f3dc4; background: #f3f0ff; font-weight: 700;"
);

const STATO_TESTO = {
  charging: "in carica",
  discharging: "in scarica",
  critical: "carica d'emergenza",
  forced: "carica forzata",
  failsafe: "fail-safe",
  disabled: "non gestito",
};

/** Classe CSS del testo di stato: solo i casi anomali si colorano. */
function classeStato(stato) {
  if (stato === "charging" || stato === "forced") return "attivo";
  if (stato === "critical" || stato === "failsafe") return "allarme";
  if (stato === "disabled") return "spento";
  return "";
}

const STILE = `
  ha-card {
    padding: 16px;
  }
  .intestazione {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 8px;
  }
  .titolo {
    font-size: 1.25rem;
    font-weight: 500;
    color: var(--primary-text-color);
  }
  .sottotitolo {
    font-size: 0.8125rem;
    color: var(--secondary-text-color);
  }
  .sottotitolo.allarme {
    color: var(--error-color);
    font-weight: 500;
  }
  .tablet {
    padding: 12px 0;
    border-top: 1px solid var(--divider-color);
  }
  .riga {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .nome {
    font-weight: 500;
    color: var(--primary-text-color);
  }
  .dettaglio {
    font-size: 0.8125rem;
    color: var(--secondary-text-color);
  }
  .dettaglio.attivo {
    color: var(--primary-color);
    font-weight: 500;
  }
  .dettaglio.allarme {
    color: var(--error-color);
    font-weight: 500;
  }
  .dettaglio.spento {
    opacity: 0.6;
  }
  .comandi {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  /* Barra della batteria: la fascia chiara e' la banda di carica scelta,
     il riempimento e' il livello attuale. */
  .barra {
    position: relative;
    height: 10px;
    border-radius: 5px;
    background: var(--divider-color);
    overflow: hidden;
    margin: 10px 0 6px;
  }
  .banda {
    position: absolute;
    top: 0;
    bottom: 0;
    background: var(--primary-color);
    opacity: 0.22;
  }
  .livello {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    background: var(--primary-color);
    border-radius: 5px 0 0 5px;
    transition: width 0.4s ease;
  }
  .livello.allarme {
    background: var(--error-color);
  }
  .livello.spento {
    background: var(--disabled-text-color, #9e9e9e);
  }
  .soglie {
    display: flex;
    gap: 16px;
    align-items: center;
    flex-wrap: wrap;
  }
  .soglia {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 150px;
    font-size: 0.75rem;
    color: var(--secondary-text-color);
  }
  .soglia input[type="range"] {
    flex: 1;
    accent-color: var(--primary-color);
  }
  .avviso {
    padding: 16px;
    color: var(--error-color);
  }
`;

class NexusTabletChargeCard extends HTMLElement {
  constructor() {
    super();
    this._costruita = false;
    this._trascinamento = false;
  }

  static getConfigElement() {
    return document.createElement("nexus-tablet-charge-card-editor");
  }

  static getStubConfig(hass) {
    const candidato = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && hass.states[id].attributes.tablets !== undefined
    );
    return { entity: candidato || "" };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Serve l'entita' di stato del gruppo (sensor.*_stato)");
    }
    this._config = config;
    this._costruita = false;
    this.innerHTML = "";
  }

  getCardSize() {
    const stato = this._hass && this._hass.states[this._config.entity];
    const tablet = stato ? (stato.attributes.tablets || []).length : 1;
    return 1 + 2 * tablet;
  }

  set hass(hass) {
    this._hass = hass;
    this._aggiorna();
  }

  // ---------------------------------------------------------------------------
  // Costruzione
  // ---------------------------------------------------------------------------
  _costruisci() {
    const card = document.createElement("ha-card");
    const stile = document.createElement("style");
    stile.textContent = STILE;
    card.appendChild(stile);

    this._el = {};

    const intestazione = document.createElement("div");
    intestazione.className = "intestazione";
    this._el.titolo = document.createElement("div");
    this._el.titolo.className = "titolo";
    this._el.sottotitolo = document.createElement("div");
    this._el.sottotitolo.className = "sottotitolo";
    intestazione.appendChild(this._el.titolo);
    intestazione.appendChild(this._el.sottotitolo);
    card.appendChild(intestazione);

    this._el.elenco = document.createElement("div");
    card.appendChild(this._el.elenco);

    this.appendChild(card);
    this._costruita = true;
  }

  _creaRiga(tablet) {
    const root = document.createElement("div");
    root.className = "tablet";

    const testa = document.createElement("div");
    testa.className = "riga";

    const testi = document.createElement("div");
    const nome = document.createElement("div");
    nome.className = "nome";
    const dettaglio = document.createElement("div");
    dettaglio.className = "dettaglio";
    testi.appendChild(nome);
    testi.appendChild(dettaglio);

    const comandi = document.createElement("div");
    comandi.className = "comandi";

    const forza = document.createElement("ha-icon-button");
    forza.setAttribute("label", "Carica ora");
    forza.innerHTML = '<ha-icon icon="mdi:battery-charging-100"></ha-icon>';

    const abilita = document.createElement("ha-switch");

    comandi.appendChild(forza);
    comandi.appendChild(abilita);
    testa.appendChild(testi);
    testa.appendChild(comandi);

    const barra = document.createElement("div");
    barra.className = "barra";
    const banda = document.createElement("div");
    banda.className = "banda";
    const livello = document.createElement("div");
    livello.className = "livello";
    barra.appendChild(banda);
    barra.appendChild(livello);

    const soglie = document.createElement("div");
    soglie.className = "soglie";
    const min = this._creaSoglia("Ricarica a");
    const max = this._creaSoglia("Stop a");
    soglie.appendChild(min.root);
    soglie.appendChild(max.root);

    root.appendChild(testa);
    root.appendChild(barra);
    root.appendChild(soglie);

    const riga = { root, nome, dettaglio, forza, abilita, banda, livello, min, max, tablet };

    forza.addEventListener("click", () => {
      this._hass.callService("button", "press", { entity_id: riga.tablet.force_button });
    });
    abilita.addEventListener("change", () => {
      const corrente = this._hass.states[riga.tablet.enable_entity];
      this._hass.callService("switch", corrente.state === "on" ? "turn_off" : "turn_on", {
        entity_id: riga.tablet.enable_entity,
      });
    });

    this._collegaSoglia(riga, min, () => riga.tablet.min_entity);
    this._collegaSoglia(riga, max, () => riga.tablet.max_entity);

    return riga;
  }

  _creaSoglia(etichetta) {
    const root = document.createElement("div");
    root.className = "soglia";
    const testo = document.createElement("span");
    testo.textContent = etichetta;
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = 5;
    slider.max = 100;
    slider.step = 1;
    const valore = document.createElement("span");
    root.appendChild(testo);
    root.appendChild(slider);
    root.appendChild(valore);
    return { root, slider, valore };
  }

  _collegaSoglia(riga, soglia, entita) {
    soglia.slider.addEventListener("pointerdown", () => (this._trascinamento = true));
    soglia.slider.addEventListener("input", () => {
      soglia.valore.textContent = `${soglia.slider.value}%`;
    });
    soglia.slider.addEventListener("change", () => {
      this._trascinamento = false;
      this._hass.callService("number", "set_value", {
        entity_id: entita(),
        value: Number(soglia.slider.value),
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Aggiornamento
  // ---------------------------------------------------------------------------
  _aggiorna() {
    if (!this._config || !this._hass) return;

    const stato = this._hass.states[this._config.entity];
    if (!stato) {
      this.innerHTML = `<ha-card><div class="avviso">Entita' ${this._config.entity} non trovata.</div></ha-card>`;
      this._costruita = false;
      return;
    }

    if (!this._costruita) this._costruisci();

    const attr = stato.attributes;
    const tablets = attr.tablets || [];

    this._el.titolo.textContent = this._config.title || attr.group || "Tablet";
    const inFailsafe = stato.state === "failsafe";
    this._el.sottotitolo.textContent = inFailsafe
      ? "fail-safe attivo"
      : `${tablets.length} dispositiv${tablets.length === 1 ? "o" : "i"}`;
    this._el.sottotitolo.classList.toggle("allarme", inFailsafe);

    // Ricostruisce solo se cambia il numero di tablet: cosi' non si azzerano
    // gli slider mentre l'utente li sta trascinando.
    if (this._el.elenco.childElementCount !== tablets.length) {
      this._el.elenco.innerHTML = "";
      this._righe = tablets.map((tablet) => this._creaRiga(tablet));
      this._righe.forEach((riga) => this._el.elenco.appendChild(riga.root));
    }

    tablets.forEach((tablet, indice) => {
      const riga = this._righe[indice];
      riga.tablet = tablet;

      const livello = tablet.level;
      const noto = livello !== null && livello !== undefined;
      const classe = classeStato(tablet.status);

      riga.nome.textContent = tablet.name;
      riga.dettaglio.textContent = noto
        ? `${Math.round(livello)}% · ${STATO_TESTO[tablet.status] || tablet.status}`
        : `livello sconosciuto · ${STATO_TESTO[tablet.status] || tablet.status}`;
      riga.dettaglio.className = `dettaglio ${classe}`;

      riga.livello.style.width = `${noto ? Math.max(0, Math.min(100, livello)) : 100}%`;
      riga.livello.className = `livello ${classe === "attivo" ? "" : classe}`;

      riga.banda.style.left = `${tablet.min_level}%`;
      riga.banda.style.width = `${Math.max(0, tablet.max_level - tablet.min_level)}%`;

      const abilitato = this._hass.states[tablet.enable_entity];
      if (abilitato) riga.abilita.checked = abilitato.state === "on";
      riga.forza.disabled = tablet.status === "disabled";

      if (!this._trascinamento) {
        riga.min.slider.value = tablet.min_level;
        riga.max.slider.value = tablet.max_level;
      }
      riga.min.valore.textContent = `${Math.round(tablet.min_level)}%`;
      riga.max.valore.textContent = `${Math.round(tablet.max_level)}%`;
    });
  }
}

// -----------------------------------------------------------------------------
// Editor visuale
// -----------------------------------------------------------------------------
const SCHEMA_EDITOR = [
  {
    name: "entity",
    required: true,
    selector: { entity: { integration: "nexus_tablet_charge", domain: "sensor" } },
  },
  { name: "title", selector: { text: {} } },
];

class NexusTabletChargeCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._aggiorna();
  }

  set hass(hass) {
    this._hass = hass;
    this._aggiorna();
  }

  _aggiorna() {
    if (!this._config || !this._hass) return;

    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.schema = SCHEMA_EDITOR;
      this._form.computeLabel = (schema) =>
        schema.name === "entity" ? "Sensore di stato del gruppo" : "Titolo (facoltativo)";
      this._form.addEventListener("value-changed", (ev) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: ev.detail.value },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }

    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

customElements.define("nexus-tablet-charge-card", NexusTabletChargeCard);
customElements.define("nexus-tablet-charge-card-editor", NexusTabletChargeCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "nexus-tablet-charge-card",
  name: "Nexus Tablet Charge",
  description: "Ciclo di carica dei tablet a muro: livello, banda e comandi.",
  preview: true,
  documentationURL: "https://github.com/Pacco24626/nexus_tablet_charge_card",
});
