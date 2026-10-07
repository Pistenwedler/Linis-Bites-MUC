"""Rossmann: Filialbestand der Laeden aus stores.json per Browser (Playwright) -> docs/rossmann.json"""
import json, os, re, sys, datetime
from playwright.sync_api import sync_playwright

BRAND = "https://www.rossmann.de/de/alle-marken/linis-bites/c/online-dachmarke_17644792"

def norm(s):
    s = str(s).lower().replace("ß", "ss")
    return re.sub(r"[^a-z0-9]", "", re.sub(r"strasse|str\.", "str", s))

def accept_cookies(page):
    for pat in (r"alle akzeptieren", r"akzeptieren", r"zustimmen"):
        try: page.get_by_role("button", name=re.compile(pat, re.I)).first.click(timeout=3000); return
        except Exception: pass

def product_links(page):
    page.goto(BRAND, wait_until="domcontentloaded", timeout=60000)
    accept_cookies(page); page.wait_for_timeout(3000)
    hrefs = page.eval_on_selector_all("a[href*='/p/']", "els => els.map(e => e.href)")
    return list(dict.fromkeys(h.split("#")[0] for h in hrefs if "linis-bites" in h.lower() and "pralini" in h.lower()))

def open_dialog(page):
    for t in (r"Verfügbarkeit in deiner Filiale", r"Filiale finden", r"Filiale wählen"):
        try: page.get_by_text(re.compile(t, re.I)).first.click(timeout=5000); return True
        except Exception: pass
    return False

def search(page, q):
    for sel in ("[role=dialog] input[type=text]", "[role=dialog] input", "input[placeholder*='Postleitzahl' i]",
                "input[placeholder*='PLZ' i]", "input[placeholder*='Ort' i]", "input[name*='plz' i]"):
        try:
            box = page.locator(sel).first
            box.click(timeout=3000); box.press("Control+A"); box.press("Backspace")
            box.press_sequentially(q, delay=70)
            try: page.locator("[role=dialog]").get_by_role("button", name=re.compile(r"Filiale finden", re.I)).first.click(timeout=2000)
            except Exception:
                try: page.get_by_role("button", name=re.compile(r"Filiale finden", re.I)).last.click(timeout=2000)
                except Exception: box.press("Enter")
            page.wait_for_timeout(5000); return True
        except Exception: continue
    return False

def parse(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith("Momentan"):
            st, blk, j = lines[i], [], i + 1
            while j < len(lines) and not lines[j].startswith(("Momentan", "Abbrechen")):
                blk.append(lines[j]); j += 1
            if len(blk) >= 2 and re.search(r"\d", blk[0]) and re.match(r"\d{5}", blk[1]):
                out.append({"street": blk[0], "plz": blk[1][:5], "text": st,
                            "inStock": "nicht verfügbar" not in st,
                            "pickup": any("Abholstation" in b for b in blk)})
            i = j
        else: i += 1
    return out

def check(page, url, wanted, query, first):
    name = url.split("linis-bites-")[-1].split("/p/")[0].replace("bio-", "").replace("-", " ")
    res = {"name": name, "url": url, "stores": [], "missing": []}
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    accept_cookies(page); page.wait_for_timeout(2500)
    if not open_dialog(page) or not search(page, query):
        res["missing"] = [w["street"] for w in wanted]; res["error"] = "Dialog/Suchfeld nicht gefunden"
        if first: page.screenshot(path="docs/debug-rossmann.png")
        return res
    found = {}
    def collect():
        for t in parse(page.inner_text("body")):
            for w in wanted:
                if norm(w["street"]) == norm(t["street"]): found[norm(w["street"])] = t
    collect()
    if first:
        page.screenshot(path="docs/debug-rossmann-1.png")
        try: res["dialog"] = page.locator("[role=dialog]").first.inner_text(timeout=2000)[:500]
        except Exception: pass
    for _ in range(2):  # bis zu 2 Zusatzsuchen fuer fehlende Laeden
        miss = [w for w in wanted if norm(w["street"]) not in found]
        if not miss: break
        search(page, f"{miss[0]['street']}, {miss[0]['plz']} München"); collect()
    if first: page.screenshot(path="docs/debug-rossmann.png")
    res["stores"] = list(found.values())
    res["missing"] = [w["street"] for w in wanted if norm(w["street"]) not in found]
    return res

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    net = []
    out = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "products": [], "error": None}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=not os.environ.get("SHOW"))
            page = b.new_context(locale="de-DE", viewport={"width": 1280, "height": 1600}).new_page()
            page.on("response", lambda r: net.append([r.status, r.url[:170]]) if len(net) < 40 and
                    r.request.resource_type in ("xhr", "fetch") and re.search(r"filial|store|market|availab|geo|search|location", r.url, re.I) else None)
            for n, u in enumerate(product_links(page)[:15]):
                out["products"].append(check(page, u, cfg["rossmann"], cfg["rossmann_search"], n == 0))
            b.close()
        if not out["products"]: out["error"] = "Keine Produkte auf der Markenseite gefunden"
    except Exception as e:
        out["error"] = repr(e); print("Rossmann Fehler:", e, file=sys.stderr)
    out["net"] = net
    json.dump(out, open("docs/rossmann.json", "w"), ensure_ascii=False, indent=1)
    print(len(out["products"]), "Rossmann-Produkte geprüft")
