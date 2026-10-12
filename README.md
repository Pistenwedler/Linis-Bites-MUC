# Lini's Bites Tracker

Prueft stuendlich (nachts nicht, siehe Nachtruhe) die dm-Filialen aus `stores.json` auf Lini's Pralinis, liest Sorten, Bilder und Online-Status von
linisbites.com und schickt per ntfy eine Push-Nachricht, wenn eine Sorte wieder da ist. Dashboard: `docs/index.html`
(GitHub Pages, Ordner /docs).

## Dateien
- `scrape.py`        Abfrage (dm + Lini's), schreibt `docs/data.json`, sendet Push
- `stores.json`      Filialen (dm aktiv, Rossmann nur vorbereitet)
- `docs/index.html`  Dashboard, liest `docs/data.json`
- `.github/workflows/update.yml`  stuendlicher Lauf (cron `7 * * * *`, mit Nachtruhe) und Test-Push per Hand
- `rossmann.py`      geparkt, siehe unten
- `docs/data.json`   aktueller Stand, wird automatisch geschrieben
- `docs/history.json` Verlauf (nur Aenderungen), wird automatisch geschrieben; Grundlage fuer Zeitstrahl und Heatmap

## Push einrichten (einmalig)
1. ntfy-App installieren (iOS/Android) und ein Thema mit einem langen, zufaelligen Namen abonnieren.
   Der Themenname ist praktisch das Passwort: nicht ins Repository, nicht in die README schreiben.
2. GitHub: Settings -> Secrets and variables -> Actions -> New repository secret
   - `NTFY_TOPIC`    = dein Themenname
   - `DASHBOARD_URL` = Link zum Dashboard (optional, oeffnet sich beim Tippen auf die Nachricht)
3. Actions -> update -> Run workflow -> Haken bei "Test-Push senden".

## Wann kommt eine Nachricht?
- Sorte war in keiner deiner dm-Filialen da und ist jetzt in mindestens einer.
- Sorte war im Lini's Online-Shop nicht verfuegbar und ist es wieder.
- Sorte ist neu bei dm (vorher nur im Online-Shop oder ganz unbekannt) und schon in mindestens einer deiner Filialen.
- Einmalig, wenn die dm-Abfrage anfaengt zu scheitern.
Bei dm-Fehlern bleibt der alte Stand erhalten, damit es keine falschen "wieder da"-Meldungen gibt.

## Sorten
Alle Pralinis, die dm in seiner Produktsuche fuehrt, werden automatisch pro Filiale verfolgt. Sorten, die es nur bei
Lini's gibt (derzeit z. B. Spekulatius und Brownie Caramel), stehen unten unter "Weitere Sorten (nur online)" mit
Online-Status. Nimmt dm eine davon auf, wandert sie von selbst in die Filialliste, und es kommt eine Push-Nachricht.
Der Haken "Nur verfuegbare Sorten zeigen" blendet die Online-Liste aus.

## Nachtruhe
Von 22:00 bis 6:59 Uhr (deutsche Zeit, Sommer- und Winterzeit) fragt der Zeitplan nicht ab. GitHub startet den Lauf
zwar weiter stuendlich, das Skript beendet sich dann aber sofort und aendert nichts. Letzter Lauf am Abend 21:07,
erster am Morgen 7:07 Uhr; was nachts passiert, meldet der Lauf um 7:07. Per Hand gestartete Laeufe (Run workflow,
Test-Push) laufen immer. Das Dashboard zeigt in der Ruhezeit "Nachtruhe bis 7 Uhr" und warnt deswegen nicht vor alten
Daten. In der Heatmap landen naechtliche Auffuellungen in der 7-Uhr-Spalte.
Zeiten aendern: `QUIET = (22, 7)` oben in `scrape.py`. Gleiche Zahlen (z. B. `(0, 0)`) schalten die Nachtruhe ab.

## Verlauf
Ab dem ersten Lauf mit dieser Version wird jede Aenderung (Sorte x Filiale: da / nicht mehr da) festgehalten.
Im Dashboard: Sortenkarte aufklappen -> Zeitstrahl pro Filiale (7/14/30 Tage) und Heatmap Wochentag x Uhrzeit.
Ein Muster-Text erscheint ab 5 beobachteten Auffuellungen. Es gibt keine Rueckschau, dm liefert keine Historie.

## Anpassen
- Filialen: `stores.json`, Abschnitt `dm` (Strasse, Hausnummer, PLZ).
- Takt: cron in `update.yml` (aktuell stuendlich, jeweils zur Minute 7).
- Nachtruhe: `QUIET` in `scrape.py` (siehe oben).

## Hinweise zum oeffentlichen Repository
- Secrets (`NTFY_TOPIC`, `DASHBOARD_URL`) bleiben auch in einem oeffentlichen Repository verborgen.
- `stores.json` zeigt, welche Filialen beobachtet werden.
- Produktbilder werden direkt von linisbites.com geladen (keine Kopien im Repository).
- dm und Lini's Website werden ueber deren oeffentliche, nicht offiziell dokumentierte Schnittstellen abgefragt.
  Stuendlich ist moderat; nicht haeufiger einstellen. Aendern die Anbieter etwas, kann die Abfrage ausfallen.

## Rossmann (geparkt)
Stand: nicht automatisiert, weil Rossmann Abfragen aus GitHubs Rechenzentren blockiert.
Test am 11.10.2026: Auch vom Heimanschluss (Windows) kam die Schutzseite. Ein Heimgeraet hilft also nicht; Rossmann ist damit beerdigt.
- Schnittstelle: `https://www.rossmann.de/storefinder/.rest/store?q=80336+Muenchen&dan=<Rossmann-Artikelnummer>`
- Antwort: XML mit `<store>`-Eintraegen (`street`, `postcode`, `pickupStation`, `productInfos/productInfo/stock`).
  `stock` ist `0` (nicht da), eine Zahl oder `5+`. Eine Suche liefert die 9 naechsten Filialen.
- Aus GitHub kommt statt XML eine Schutzseite (HTML). `rossmann.py` meldet dann "Antwort ohne Filialen".
- Artikelnummern stehen in `stores.json` (`rossmann_products`). Die Zuordnung zu Sorten ist nur fuer
  White Raspberry Cake (229836) sicher geprueft. Die Nummer steht auf jeder Rossmann-Produktseite unter "Artikelnummer".
- Ideen fuer spaeter: Lauf auf einem Heimgeraet (PC mit Aufgabenplanung, Raspberry Pi) oder nur Links im Dashboard.
  Das Skript schreibt `docs/rossmann.json`; das Dashboard liest diese Datei aktuell nicht.

## Aenderungen
- 1.1 (11.10.2026): Nachtruhe 22-7 Uhr; Push, wenn eine Sorte neu bei dm auftaucht; Dashboard beruecksichtigt die Nachtruhe.
- 1.0: erste Version.
