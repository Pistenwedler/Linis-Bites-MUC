"""Test: findet die dm-Schnittstelle fuer den Filialbestand -> docs/dm_probe.json"""
import json, re
from playwright.sync_api import sync_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
URL = "https://www.dm.de/p/d/1714108/linis-bites-pralinis-raspberry-almond"
net, log, bodies = [], [], {}
SKIP = r"google|doubleclick|analytics|facebook|mapbox|criteo|tiktok|pinterest|usercentrics|consent|bazaarvoice|dy-api|stars\.services|assets\.dm|content"
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, locale="de-DE", timezone_id="Europe/Berlin", viewport={"width": 1280, "height": 1600})
        page = ctx.new_page()
        page.on("response", lambda r: net.append([r.status, r.url[:220]]) if len(net) < 80 and
                r.request.resource_type in ("xhr", "fetch") and not re.search(SKIP, r.url, re.I) else None)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(4000)
        try: page.get_by_role("button", name="Alles akzeptieren").first.click(timeout=6000); log.append("cookies ok")
        except Exception: log.append("cookies nicht gefunden")
        page.wait_for_timeout(2000); page.evaluate("window.scrollTo(0,0)")
        try:
            txt = page.eval_on_selector_all("button, a", "els => els.map(e => (e.innerText||'').trim())")
            log.append("buttons: " + " | ".join(dict.fromkeys(t for t in txt if t and len(t) < 70))[:1500])
        except Exception: pass
        done = False
        for pat in (r"Markt", r"Verfügbarkeit", r"Filiale", r"Ändern"):
            for fn in (lambda: page.get_by_role("button", name=re.compile(pat, re.I)).first,
                       lambda: page.get_by_text(re.compile(pat, re.I)).first):
                try: fn().click(timeout=3000); log.append("klick " + pat); done = True; break
                except Exception: pass
            if done: break
        page.wait_for_timeout(3000)
        for sel in ("input:visible",):
            try:
                box = page.locator(sel).first; box.click(timeout=3000); box.press("Control+A")
                box.press_sequentially("Theresienhöhe 5, 80339 München", delay=70); box.press("Enter")
                page.wait_for_timeout(7000); log.append("suche ok")
            except Exception: log.append("kein Eingabefeld")
        page.screenshot(path="docs/debug-dm.png")
        for u in ("https://products.dm.de/availability/api/v2/detail/DE/1714108",
                  "https://products.dm.de/availability/api/v2/tiles/DE/1714108"):
            try: bodies[u] = page.request.get(u).text()[:1200]
            except Exception as e: bodies[u] = "Fehler " + repr(e)[:100]
        b.close()
except Exception as e:
    log.append("Fehler " + repr(e)[:200])
json.dump({"log": log, "net": net, "bodies": bodies}, open("docs/dm_probe.json", "w"), ensure_ascii=False, indent=1)
print("dm_probe fertig", log)
