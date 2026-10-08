# Lini's Bites Tracker

Prueft stuendlich die dm-Filialen aus `stores.json` auf Lini's Pralinis, liest Sorten, Bilder und Online-Status von
linisbites.com und schickt per ntfy eine Push-Nachricht, wenn eine Sorte wieder da ist. Dashboard: `docs/index.html`
(GitHub Pages, Ordner /docs).

## Dateien
- `scrape.py`        Abfrage (dm + Lini's), schreibt `docs/data.json`, sendet Push
- `stores.json`      Filialen (dm aktiv, Rossmann nur vorbereitet)
- `docs/index.html`  Dashboard, liest `docs/data.json`
- `.github/workflows/update.yml`  stuendlicher Lauf (cron `7 * * * *`) und Test-Push per Hand
- `rossmann.py`      geparkt, siehe unten
- `docs/data.json`   wird automatisch geschrieben, nicht von Hand aendern

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
- Einmalig, wenn die dm-Abfrage anfaengt zu scheitern.
Bei dm-Fehlern bleibt der alte Stand erhalten, damit es keine falschen "wieder da"-Meldungen gibt.

## Anpassen
- Filialen: `stores.json`, Abschnitt `dm` (Strasse, Hausnummer, PLZ).
- Takt: cron in `update.yml` (aktuell stuendlich, jeweils zur Minute 7).

## Hinweise zum oeffentlichen Repository
- Secrets (`NTFY_TOPIC`, `DASHBOARD_URL`) bleiben auch in einem oeffentlichen Repository verborgen.
- `stores.json` zeigt, welche Filialen beobachtet werden.
- Produktbilder werden direkt von linisbites.com geladen (keine Kopien im Repository).
- dm und Lini's Website werden ueber deren oeffentliche, nicht offiziell dokumentierte Schnittstellen abgefragt.
  Stuendlich ist moderat; nicht haeufiger einstellen. Aendern die Anbieter etwas, kann die Abfrage ausfallen.

## Rossmann (geparkt)
Stand: nicht automatisiert, weil Rossmann Abfragen aus GitHubs Rechenzentren blockiert.
Von einem normalen Heimanschluss aus funktioniert die Abfrage.
- Schnittstelle: `https://www.rossmann.de/storefinder/.rest/store?q=80336+Muenchen&dan=<Rossmann-Artikelnummer>`
- Antwort: XML mit `<store>`-Eintraegen (`street`, `postcode`, `pickupStation`, `productInfos/productInfo/stock`).
  `stock` ist `0` (nicht da), eine Zahl oder `5+`. Eine Suche liefert die 9 naechsten Filialen.
- Aus GitHub kommt statt XML eine Schutzseite (HTML). `rossmann.py` meldet dann "Antwort ohne Filialen".
- Artikelnummern stehen in `stores.json` (`rossmann_products`). Die Zuordnung zu Sorten ist nur fuer
  White Raspberry Cake (229836) sicher geprueft. Die Nummer steht auf jeder Rossmann-Produktseite unter "Artikelnummer".
- Ideen fuer spaeter: Lauf auf einem Heimgeraet (PC mit Aufgabenplanung, Raspberry Pi) oder nur Links im Dashboard.
  Das Skript schreibt `docs/rossmann.json`; das Dashboard liest diese Datei aktuell nicht.
