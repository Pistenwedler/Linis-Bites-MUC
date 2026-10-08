"""dm-Filialverfuegbarkeit fuer die Laeden aus stores.json -> docs/data.json"""
import json, math, re, datetime, urllib.request, urllib.parse, urllib.error, sys

CENTER = (48.1340, 11.5666)  # Sendlinger Tor, nur fuer Entfernungsanzeige/Suchgebiet
DM_BRAND_URL = "https://www.dm.de/marken/linis-bites-2349676"
DM_FALLBACK = {"3121779": "Vanilla Cookie", "3121805": "Carrot Cake", "3121823": "Tiramisu"}
LINKS = {
    "Rossmann: alle Lini's Bites": "https://www.rossmann.de/de/alle-marken/linis-bites/c/online-dachmarke_17644792",
    "Edeka Marktsuche (kein Bestand abrufbar)": "https://www.edeka.de/marktsuche.jsp",
    "Alnatura Marktfinder (kein Bestand abrufbar)": "https://www.alnatura.de/de-de/maerkte/marktfinder/",
}
UA = {"User-Agent": "Mozilla/5.0 (private hobby tracker)", "Accept": "application/json, text/html"}

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

DEBUG = []
def get(url):
    try:
        data = json.loads(fetch(url)); DEBUG.append(["ok", url[:170]]); return data
    except urllib.error.HTTPError as e:
        DEBUG.append([e.code, url[:170], e.read().decode("utf-8", "replace")[:200]]); raise
    except Exception as e:
        DEBUG.append(["err", url[:170], repr(e)[:150]]); raise

def norm(s):
    s = str(s).lower().replace("ß", "ss")
    s = re.sub(r"strasse|str\.", "str", s)
    return re.sub(r"[^a-z0-9]", "", s)

def km(lat, lng):
    p = math.pi / 180; la, lo = CENTER
    a = 0.5 - math.cos((lat-la)*p)/2 + math.cos(la*p)*math.cos(lat*p)*(1-math.cos((lng-lo)*p))/2
    return 12742 * math.asin(math.sqrt(a))

def dm_search():
    prods = {}
    try:
        res = get("https://product-search.services.dmtech.com/de/search/static?" +
                  urllib.parse.urlencode({"query": "lini's bites pralinis", "pageSize": 40}))
        for p in res.get("products", []):
            dan = p.get("dan") or p.get("dmid"); t = str(p.get("title") or p.get("name") or "")
            if dan and "lini" in (str(p.get("brandName", "")) + t).lower() and "pralini" in t.lower():
                prods[str(dan)] = re.sub(r"Lini.s Bites|Pralinis|,\s*\d+ g", "", t).strip() or str(dan)
    except Exception as e:
        print("dm Suche:", e, file=sys.stderr)
    return prods

def dm_products():
    prods = dm_search()
    if prods: return {**DM_FALLBACK, **prods}
    try:
        html = fetch(DM_BRAND_URL)
        for dan in dict.fromkeys(re.findall(r"/p/d/(\d{5,8})", html)):
            try: t = re.search(r"<title>(.*?)</title>", fetch(f"https://www.dm.de/p/d/{dan}/"), re.S).group(1)
            except Exception: t = ""
            if "pralini" in t.lower() or not t:
                prods[dan] = re.sub(r"Lini.s Bites|Pralinis|\| dm.*|,\s*\d+ g", "", t).strip() or dan
    except Exception as e:
        print("dm Produktsuche:", e, file=sys.stderr)
    return prods or DM_FALLBACK

def dm_stores(wanted):
    allst = {}
    for la, lo, rad in ((CENTER[0], CENTER[1], 8), (48.1400, 11.5100, 3), (48.1195, 11.5455, 3)):
        try:
            data = get(f"https://store-data-service.services.dmtech.com/stores/nearby/{la:.5f},{lo:.5f}/{rad}?countryCode=DE")
            for x in (data.get("stores", data) if isinstance(data, dict) else data):
                allst[str(x.get("storeNumber"))] = x
        except Exception: continue
    stores = list(allst.values()); DEBUG.append(["dm_stores_gefunden", len(stores)])
    if not stores: raise RuntimeError("keine dm-Filialliste abrufbar (siehe dm_debug)")
    found, unmatched = [], []
    for w in wanted:
        hit = None
        for s in stores:
            blob = norm(" ".join(str(v) for v in (s.get("address") or {}).values()))
            if norm(w["street"]) in blob and norm(w["no"]) in blob and w["plz"] in blob:
                hit = s; break
        label = f"dm {w['street']} {w['no']}"
        if not hit: unmatched.append(label); continue
        loc = hit.get("location", {}); lat, lng = loc.get("lat"), loc.get("lon", loc.get("lng"))
        found.append({"id": str(hit.get("storeNumber")), "sid": str(hit.get("storeId") or ""), "name": label,
                      "dist": round(km(lat, lng), 2) if lat else None})
    return found, unmatched

def find(data, sid):
    """Sucht den Eintrag zu einer Filial-ID in beliebig verschachtelter Antwort."""
    if isinstance(data, dict):
        if sid in data: return data[sid]
        if sid in [str(v) for v in data.values() if isinstance(v, (str, int))]: return data
        for v in data.values():
            r = find(v, sid)
            if r is not None: return r
    elif isinstance(data, list):
        for v in data:
            r = find(v, sid)
            if r is not None: return r
    return None

def judge(v):
    txt = json.dumps(v, ensure_ascii=False).upper()
    level = None
    if isinstance(v, dict):
        for k in ("stockLevel", "stock", "quantity", "amount"):
            if isinstance(v.get(k), (int, float)): level = int(v[k]); break
    ok = "GREEN" in txt or '"INSTOCK": TRUE' in txt or bool(level)
    return {"inStock": ok, "level": level, "text": f"{level} Stück" if level else ""}

def dm_availability(stores, prods):
    ids = ",".join(x["sid"] for x in stores if x.get("sid"))
    for x in stores: x["items"] = {}
    first = True
    for dan, name in prods.items():
        try: data = get(f"https://products.dm.de/availability/api/v2/map/basic/DE/{dan}/{ids}")
        except Exception: continue
        if first: DEBUG.append(["dm_antwort_beispiel", json.dumps(data, ensure_ascii=False)[:700]]); first = False
        for x in stores:
            v = find(data, x["sid"])
            if v is not None: x["items"][name] = judge(v)
    return stores

if __name__ == "__main__":
    cfg = json.load(open("stores.json"))
    r = {"updated": datetime.datetime.utcnow().isoformat() + "Z", "dm": [], "dm_error": None,
         "dm_unmatched": [], "links": LINKS}
    try:
        prods = dm_products(); r["dm_products"] = prods
        stores, r["dm_unmatched"] = dm_stores(cfg["dm"])
        r["dm"] = dm_availability(stores, prods) if stores else []
        if r["dm"] and not any(x["items"] for x in r["dm"]): r["dm_error"] = "Bestandsantwort nicht erkannt (siehe dm_debug)"
    except Exception as e:
        r["dm_error"] = repr(e); print("dm Fehler:", e, file=sys.stderr)
    r["dm_debug"] = DEBUG[-20:]
    json.dump(r, open("docs/data.json", "w"), ensure_ascii=False, indent=1)
    print(len(r["dm"]), "dm-Filialen geprüft; nicht zugeordnet:", r["dm_unmatched"])
