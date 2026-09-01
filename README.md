# Nexus Tablet Charge

Gestione del ciclo di carica dei tablet a muro in Home Assistant, configurabile
interamente dall'interfaccia. Serve a non lasciare un tablet perennemente
attaccato al caricatore.

## Perché

Una cella al litio tenuta stabilmente al 100% invecchia molto più in fretta di una
che lavora in una banda intermedia. Su un tablet incassato a muro, sostituire la
batteria significa smontare il pannello: conviene evitare di doverlo fare.

Questa integrazione tiene la batteria fra due soglie — sotto la minima accende il
caricatore, sopra la massima lo spegne — comandando l'uscita elettrica a cui è
collegato il caricabatterie.

## Requisiti

- **Companion app di Home Assistant** installata sul tablet, con i sensori di
  batteria abilitati in *Impostazioni app → Sensori*. È l'unica fonte del livello
  di carica: senza, l'integrazione non ha nulla da leggere.
- Un'uscita comandabile (`switch` o `light`) che alimenta il caricatore.
- Home Assistant 2024.12 o superiore.

> Su iPad: la companion app è l'unica strada. Fully Kiosk Browser non esiste per
> iOS, e Safari non pubblica sensori verso Home Assistant.

## Installazione via HACS

1. HACS → menu ⋮ → **Repository personalizzate**
2. URL `https://github.com/Pacco24626/nexus_tablet_charge`, categoria **Integration**
3. Installa, poi **riavvia Home Assistant**
4. **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Nexus Tablet Charge**

## Configurazione

1. **Nome gruppo** — puoi creare più gruppi se gestisci impianti diversi.
2. **Tablet** — nome, sensore batteria, uscita del caricatore, soglie. La spunta
   *"Aggiungi un altro tablet"* ricicla lo step: nessun limite al numero di tablet.
3. **Protezioni** — soglia critica e ore di silenzio prima del fail-safe.

Tutto rimodificabile da **Configura** senza reinstallare.

## Entità generate

Per ogni tablet:

| Entità | Descrizione |
|---|---|
| `number.<tablet>_soglia_di_ricarica` | Sotto questo livello il caricatore si accende |
| `number.<tablet>_soglia_di_stop` | Sopra questo livello si spegne |
| `switch.<tablet>_gestione_carica` | Spento, l'integrazione non tocca il caricatore |
| `button.<tablet>_carica_ora` | Carica fino alla soglia di stop, poi torna al ciclo |
| `sensor.<tablet>_stato` | `charging` / `discharging` / `critical` / `forced` / `failsafe` / `disabled` |

Più, per il gruppo, `sensor.<gruppo>_stato`, che porta negli attributi la mappa
completa usata dalla card.

## Le tre protezioni

**Banda morta.** Fra le due soglie lo stato del caricatore viene mantenuto, non
ricalcolato. È ciò che impedisce al relè dell'attuatore di ticchettare avanti e
indietro sul valore di soglia. Prima di ogni comando si verifica che lo stato
debba cambiare davvero.

**Soglia critica.** Sotto il livello critico si carica comunque, ignorando ogni
altra condizione tranne la disabilitazione manuale.

**Fail-safe sul sensore.** Se il sensore diventa non disponibile, o smette di
riportare per più delle ore configurate, il caricatore **viene acceso** e arriva una
notifica. È deliberato: il modo peggiore di sbagliare è lasciare il caricatore
spento non sapendo a che punto è la batteria, perché il tablet si scarica, muore, e
il pannello a muro resta nero finché qualcuno non se ne accorge. La notifica viene
ritirata da sola quando il sensore torna a parlare.

## Tarare `stale_hours` sul campo

Su iOS il sistema sospende le app in background: quando lo schermo del tablet è
spento, i sensori della companion app si aggiornano molto più di rado. Se la
cadenza reale supera le ore configurate, il fail-safe scatta di continuo e il
caricatore resta acceso in permanenza — cioè esattamente ciò che si voleva evitare.

Sul tablet servono **Aggiornamento app in background** attivo e permesso di
posizione **"Sempre"**. Poi tieni d'occhio per un giorno la cronologia del sensore
di batteria: se vedi buchi da quattro o cinque ore, alza `stale_hours` di
conseguenza. Il parametro esiste per questo.

## Card dedicata

[Nexus Tablet Charge Card](https://github.com/Pacco24626/nexus_tablet_charge_card) —
facoltativa. Senza, il gruppo si comanda con le card standard.
