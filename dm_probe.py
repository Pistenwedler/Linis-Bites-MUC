"""Einmaliger Test: findet heraus, welche Schnittstelle dm fuer den Filialbestand benutzt -> docs/dm_probe.json"""
import json, re, sys
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
URL = "https://www.dm.de/p/d/1714108/linis-bites-pralinis-raspberry-almond"
net, log = [], []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, locale="de-DE", timezone_id="Europe/Berlin", viewport={"width": 1280, "height": 1600})
        page = ctx.new_page()
        page.on("response", lambda r: net.append([r.status, r.url[:220]]) if len(net) < 80 and
                r.request.resource_type in ("xhr", "fetch") and
                not re.search(r"google|doubleclick|analytics|facebook|mapbox|criteo|tiktok|pinterest|usercentrics|consent", r.url, re.I) else None)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        for pat in (r"Alle akzeptieren|Alle Cookies akzeptieren|Akzeptieren",):
            try: page.get_by_text(re.compile(pat, re.I)).first.click(timeout=4000); log.append("cookies ok")
            except Exception: log.append("cookies nicht gefunden")
        page.wait_for_timeout(1500)
        for pat in (r"Verfügbarkeit", r"dm-Markt", r"Markt wählen"):
            try: page.get_by_text(re.compile(pat, re.I)).first.click(timeout=4000); log.append("klick " + pat); break
            except Exception: log.append("kein Klick " + pat)
        page.wait_for_timeout(2500)
        for sel in ("[role=dialog] input", "input[type=search]", "input[type=text]"):
            try:
                box = page.locator(sel).first; box.click(timeout=3000); box.press("Control+A")
                box.press_sequentially("Theresienhöhe 5, 80339 München", delay=70); box.press("Enter")
                page.wait_for_timeout(6000); log.append("suche " + sel); break
            except Exception: log.append("kein Feld " + sel)
        page.screenshot(path="docs/debug-dm.png"); b.close()
except Exception as e:
    log.append("Fehler " + repr(e)[:200])
json.dump({"log": log, "net": net}, open("docs/dm_probe.json", "w"), ensure_ascii=False, indent=1)
print("dm_probe fertig", log)
