# Lini's Bites Tracker

Prueft die Laeden aus stores.json (dm + Rossmann). Laeden aendern: stores.json bearbeiten.
Edeka/Alnatura nur als Links. Rewe entfaellt. Ergebnis: docs/index.html (liest docs/data.json + docs/rossmann.json).

## A) Lokal testen (empfohlen als erstes, ca. 10 Min.)
1. Python 3.10+ installieren (python.org).
2. Terminal im Ordner dieses Pakets oeffnen.
3. dm + Rewe:      python scrape.py
4. Rossmann:       pip install playwright
                   playwright install chromium
                   python rossmann.py
   (Browser sichtbar machen: Windows `set SHOW=1`, Mac/Linux `SHOW=1 python rossmann.py`)
5. Dashboard ansehen: python -m http.server -d docs  -> Browser: http://localhost:8000
   (index.html nicht per Doppelklick oeffnen, dann blockiert der Browser die Daten.)

## B) GitHub (automatisch)
1. Neues Repository anlegen (Private moeglich), alle Dateien inkl. Ordner .github hochladen.
2. Actions -> "update" -> Run workflow.
3. Laeuft danach alle 2 Tage (Cron in .github/workflows/update.yml).
4. Dashboard: Settings -> Pages -> Branch main, Ordner /docs.
   ACHTUNG: GitHub Pages fuer PRIVATE Repos braucht einen bezahlten Plan (z. B. Pro).
   Kostenlos nur bei Public Repo (hier stehen keine Passwoerter/Geheimnisse drin).
   Alternative bei Private/Free: Dateien aus docs/ herunterladen und lokal wie unter A) ansehen.

## Wenn etwas nicht klappt
Fehlermeldungen stehen im Dashboard bzw. in docs/data.json / docs/rossmann.json.
Screenshot der Rossmann-Seite: docs/debug-rossmann.png.
